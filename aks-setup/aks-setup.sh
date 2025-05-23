#!/bin/bash

# change to the directory where the OpenTofu script is located
cd tofu-aks

# ensure the plan runs successfully
echo "Planning to create a new AKS cluster"
tofu plan --out plan

# apply the plan
echo "Applying the plan to create the AKS cluster"
tofu apply plan

# store the cluster name in an environment variable
export AKS_CLUSTER=$(tofu output -raw kubernetes_cluster_name)

# store the resource group name in an environment variable
export AKS_RC=$(tofu output -raw resource_group_name)

echo "AKS cluster name: $AKS_CLUSTER"
echo "AKS resource group name: $AKS_RC"

# add the AKS context to the kubeconfig file
echo "Creating a new context in the default kubeconfig file"
az aks get-credentials --resource-group $AKS_RC --name $AKS_CLUSTER --context west-cluster

# change to the directory where the K8s configs are located
cd ../

# install NATS
echo "Installing NATS"
helm upgrade --install nats-west nats/nats -f aks-nats-values.yaml

# install cert-manager
echo "Installing cert-manager"
helm repo add jetstack https://charts.jetstack.io --force-update
helm install \
  cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.17.2 \
  --set crds.enabled=true