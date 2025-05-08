import asyncio
import json
import os
import ssl
import nats
import nats.micro

class SubtractorService():
    async def operate(self, msg: nats.aio.msg):
        try:
            print(f"Received request: {msg.data.decode()}")
            # Parse the request
            data = json.loads(msg.data.decode())
            data["result"] = data["first"] - data["second"]
            
            # Respond with the result
            await msg.respond(json.dumps(data).encode())
        except Exception as e:
            await msg.respond(f"Error: {str(e)}".encode())

async def main():

    region = os.environ.get("REGION")
    server_urls = os.environ.get("NATS_SERVERS").split(",")
    if not server_urls:
        raise ValueError("NATS_SERVERS environment variable is not set or empty.")
    else:
        server_urls = [url.strip() for url in server_urls]
        print(f"Using NATS servers: {server_urls}")

    ssl_ctx = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH,
        cafile="/etc/nats/tls/ca.crt"
    )
    ssl_ctx.load_cert_chain(
        certfile="/etc/nats/tls/tls.crt",
        keyfile="/etc/nats/tls/tls.key"
    )
    
    # Load schemas
    schemas_folder = os.path.join(os.path.dirname(__file__), "schemas")
    with open(os.path.join(schemas_folder, "endpoint-schema.json"), "r") as file:
        endpoint_schema = file.read()
    with open(os.path.join(schemas_folder, "response-schema.json"), "r") as file:
        response_schema = file.read()
    
    print(f"Connecting to NATS servers: {server_urls}")
    # Connect to NATS server
    nc = await nats.connect(servers=server_urls, tls=ssl_ctx)

    # Create the SubtractorService
    svc = await nats.micro.add_service(nc, name=f"SubtractorService_{region}", version="1.0.0", description="Subtract the second number from the first")
    adder = SubtractorService()
    group = svc.add_group(name="math")
    await group.add_endpoint(name="subtract", handler=adder.operate, subject="numbers.subtract", metadata={"endpoint_schema": endpoint_schema, "response_schema": response_schema})

    # Start the service
    await svc.start()
    print("SubtractorService is running...")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down SubtractorService...")
        await svc.stop()
        await nc.close()

if __name__ == "__main__":
    asyncio.run(main())