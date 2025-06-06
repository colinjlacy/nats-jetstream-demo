# NATS SuperCluster and Services Framework Demo

This repo builds out and runs requests against a NATS SuperCluster running in AWS and Azure. The goal of this demo:

- show how a SuperCluster can span multiple cloud environments over the internet
- give examples for how to use the Services Framework to build NATS-connected services
- demonstrate how geo-affinity keeps traffic locally-blound when possible to avoid latency

## The folder structure

- `/aks-setup`: OpenTofu and Kubernetes configuration files specific to the Azure environment running in `westus`
- `/eks-setup`: OpenTofu and Kubernetes configuration files specific to the AWS environment running in `us-east-1`
- `/k8s-configs`: the Kubernetes configuration files used to deploy services into both environments
- `/services`: the Python code for the various services that are used for the demo
- `/jetstream`: OpenTofu configurations for managing Streams and Consumers in JetStream

## Some FYI

This is project meant for demo purposes only. While it employs authenticationa and authorization for all of the exposed endpoints that it creates, the authentication credentials are stored in this repo and are therefore insecure. Deploy this repo only in ad hoc environments that you can stand up and tear down without impacting your production environments. **Do not run this project in its current state in production.**

## Setting up the environments

Both the Azure and AWS environments are set up using a Bash script, which can be found in their respective folders.

**NOTE: This assumes that you have the [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) and [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) installed and configured with a user/role/subscription that has the privileges to create resources in the two regions listed above. You will also need the [eksctl](https://eksctl.io/installation/) CLI installed in order to provision a service account for the AWS Load Balancer Controller.**

**NOTE: This also assumes that you have [OpenTofu](https://opentofu.org/docs/intro/install/) installed, and are running at least version 1.8.** At the time that this was created, the OpenTofu configs don't use any syntax that would impact compatibility with [Terraform](https://www.terraform.io/), so you should be able to use either IaC tool. Consider using [tenv](https://github.com/tofuutils/tenv) if you need to swap between tools or versions.

### Azure

To set up the Azure environment, `cd` into the `/aks-setup` folder and run:

```sh
sh aks-setup.sh
```

This will:
- run the OpenTofu configs that build out the AKS environment
- add a new context to your default kubeconfig file called `west-cluster` and set it as the current context
- run the Helm install command to build out the NATS cluster under the release name `nats-west`

### AWS

To set up the AWS environment, `cd` into the `/eks-setup` folder and run:

```sh
sh eks-setup.sh
```

This will:
- run the OpenTofu configs that build out the EKS environment
- add a new context to your default kubeconfig file called `east-cluster` and set it as the current context
- set the default storage class, as EKS doesn't specify one on creation
- creates an IAM service account to for the AWS Load Balancer Controller
- installs the AWS Load Balancer Controller
- run the Helm install command to build out the NATS cluster under the release name `nats-east`

#### A note about EKS

When AWS adds a new context to your default kubeconfig, it uses the AWS CLI to authenticate each request made by kubectl. If you want to use a Kubernetes UI like [Lens](https://k8slens.dev/) to interact with your clusters, you'll need to create a separate kubeconfig file. The script and K8s config file necessary to do that have been provided in `/eks-setup/kubeconfig-setup`. Assuming you have the EKS cluster set as your current context, run the following from the `/eks-setup` directory:

```sh
kubectl apply -f kubeconfig-setup/admin-sa.yaml
sh kubeconfig-setup/create-sa-token.sh
```

That will create a kubeconfig file tied to a ServiceAccount that has cluster-admin priviliges. You can then load that into Lens as a new kubeconfig file.

## NATS Gateways and Cluster Connectivity

In a production environment, you'd likely already have a domain name associated with your K8s cluster ingress that you can map to the service used by the NATS servers.

However, since this is just a demo, we avoided forcing you to provide that domain name in either cloud, and instead are just relying on the auto-generated hostname and IP of the load balancers created by each cloud provider. With that in mind, **we have to deploy the NATS Helm chart before we can know what the connectivity endpoint for the exposed load balancer is.**

If you look in `/aks-setup/aks-nats-values.yaml` and `/eks-setup/eks-nats-values.yaml`, you'll notice that the `gateway` block has been commented out, for this reason. You'll need to see what endpoint is generated by each cloud provider, fill in that endpoint in each `values.yaml` file, and run `helm upgrade...` on each release of NATS.

Again, in production, you likely wouldn't have to do this.

The quickest way to get this information is to run the following against the AWS context:

```sh
kubectl get svc nats-east -o json | jq .status.loadBalancer.ingress
```

That will print out a hostname that you can use as the endpoint for your gateway in AWS.

For Azure:

```sh
kubectl get svc nats-east -o json | jq .status.loadBalancer.ingress
```

That will print out the IP that you can use as the endpoint for your gateway in Azure.

If you don't have `jq` installed, you can find it here: https://jqlang.org/

Otherwise you can just run `kubectl get svc nats-east -o json` and sift through the output.

## TLS Connections

This project deviates from the [previous one](https://github.com/colinjlacy/nats-cluster-demo) by [using mTLS](https://docs.nats.io/running-a-nats-service/configuration/securing_nats/tls) to connect services to the NATS resources running in each Kubernetes cluster. 

**Please keep in mind that this approach is for demo purposes, and is not necessarily recommended for production use. Check with your team and business to see what security and compliance requirements exist for using TLS certs within your organization.**

To get started, deploy cert-manager into each Kubernetes cluster. You can find installation instructions [on the cert-manager website](https://cert-manager.io/docs/installation/helm/).

Once you have that installed, you can start creating certs to match your deployment stack. Each Kubernetes cluster requires its own cert heirarchy, since they'll each use TLS for connecting internally. In a production setting, you would use a common Certificate Authority (CA) to create certs within each cluster, so that they could all reference the same heirarchy. For now, and for this demo, cluster-specific CA's will do.

In each setup folder, you'll see a YAML file for setting up certs - `nats-tls-east.yaml` in `eks-setup/` and `nats-tls-west.yaml` in `aks-setup/`. Each one is *almost* ready to use. However they each need the public endpoint of the load balancer used to expose NATS to the public internet. This is important because without this, you won't be able to create a NATS context in the CLI, nor connect locally using OpenTofu to create JetStream resources.

In `eks-setup/nats-tls-east.yaml`, populate line 55 with the hostname of the NLB that was used to expose NATS.

In `aks-setup/nats-tls-west.yaml`, populate line 56 with the IP of the Azure Load Balancer that was used to expose NATS.

Now apply each one to their respective clusters. It should create a series of Secret resources in each cluster. Note that all of the service Deployment and Job YAML files have been updated to reference these Secret resources and pull in their values. You don't have to do anything there.

## JetStream Streams and Consumers

With TLS certs all set up, you can start to set up JetStream. First, you'll need to pull down the values in the `nats-admin-tls` Secret, and store each in the respective cluster's folder. So, for example, for EKS you would pull each entry from `secrets/nats-admin-tls` - `tls.ca`, `tls.crt`, and `tls.key` - and store each one in a file bearing that name in `jetstream/eks/`. The environment folders have a `.gitkeep` to make sure they are there when you pull down this repo. Once your done, there should be three files in each folder, e.g.:

- `jetstream/eks/tls.ca`
- `jetstream/eks/tls.cert`
- `jetstream/eks/tls.key`

**You'll also need to populate the different `tfvars` files with the public endpoint of the NATS server, provided by the cloud load balancer - the NLB hostname for EKS, and the IP for Azure.** A placeholder and comment has been added to the top of each `tfvars` file, and needs to be replaced.

With those in place you should be able to run the OpenTofu configs, for example, against EKS:

```sh
tofu init --var-file=eks.tfvars
tofu plan --out plan --var-file eks.tfvars
tofu apply plan
```

## Deploying the Services

When configured against either context, you can deploy the services in bulk by running:

```sh
kubectl apply -f k8s-configs
```

This will run all four mathmatical services as Deployments with 3 instances, as well as the requester Job. Note that the requester Job will deploy and possibly run before the other services are ready, so you may need to run it again to see intended results:

```sh
kubectl replace -f k8s-configs/requester.yaml --force
```

## NATS Context

The NATS CLI requires a context to connect to when it needs to communicate with a remote cluster. In order to set it up, we can use the same TLS credentials that we used in OpenTofu. We'll use the absolute paths for the TLS files, so that when you run the NATS CLI against this context, you can run it from anywhere in your file structure. The following is for creating a context against the Azure load balancer:

```sh
nats context add west --select --tlsca=/absolute/path/to/jetstream/aks/tls.ca --tlscert=/absolute/path/to/jetstream/aks/tls.crt --tlskey=/absolute/path/to/jetstream/aks/tls.key -s <azure-lb-ip> --description=Azure_US_West
```

You'll want to replace the file paths with your own file paths, and replace the `<azure-lb-ip>` placeholder with the actual IP of the Azure LB. You would then do the same for EKS, pointing to the AWS NLB hostname for the `-s` value, and using the file paths for the EKS TLS files.

## Running the Recorder in Kubernetes

The Recorder service has its own deployment YAML that will work against a properly set up K8s cluster. However you'll have to make sure that there's a MySQL database accessible from he Kubernetes cluster in order to properly run it.

For that I used the [Bitnami MySQL Helm Chart](https://artifacthub.io/packages/helm/bitnami/mysql).

Whatever solution you decide to go with, be sure to update the ConfigMap in `k8s-configs/recorder.yaml`.

## Running the Recorder Locally

This is a bit more involved. You'll need to have a MySQL database stood up locally for the Recorder to connect to. I used a simple local installation of MySQL Server, which allowed for unauthenticated connectivity. Whatever solution you choose, be sure to update the default values in `services/recorder/main.py`.

**Remember to create the schema and tables that will be used for storing data!**

You'll also need to pull down the TLS credentials that the Recorder service uses, which are stored in `secrets/nats-recorder-tls` in your Kubernetes cluster. Those are expected to be stored in their respective files alongside the `main.py` in the `services/recorder` folder, so:

- services/recorder/tls.ca
- services/recorder/tls.cert
- services/recorder/tls.key

With those all set up, you can run the Recorder

## Environment teardown

The Azure environment can be entirely torn down by `cd`ing into the `aks-setup/tofu-aks` folder and running:

```
tofu destroy --auto-approve
```

The AWS environment is a little more complex to tear down, and the Elastic Load Balancer can be a little finicky when you try to delete it. Additionally, the CloudFormation stack used to create the service account used by the Load Balancer Controller (provisioned by `eksctl`) needs to be removed as well. For that reason, a script has been created to tear down the AWS environment:

``
cd eks-setup
sh eks-teardown.sh
``

## Further Resources

- NATS Helm Chart: https://github.com/nats-io/k8s/blob/main/helm/charts/nats/README.md
- NATS By Example: https://natsbyexample.com/examples/services/intro/go
- NATS TLS Setup Example: https://github.com/nats-io/nack/tree/main/examples/secure
- NATS docs on JetStream: https://docs.nats.io/nats-concepts/jetstream
- NATS JetStream OpenTofu provider: https://search.opentofu.org/provider/nats-io/jetstream/latest

