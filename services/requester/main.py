import os
import json
import asyncio
import random
from nats.aio.client import Client as NATS

async def main():
    # Connect to the NATS cluster
    server_urls = os.environ.get("NATS_SERVERS").split(",")
    if not server_urls:
        raise ValueError("NATS_SERVERS environment variable is not set or empty.")
    else:
        server_urls = [url.strip() for url in server_urls]
        print(f"Using NATS servers: {server_urls}")
    # nats_user = os.environ.get("NATS_USER")
    # nats_password = os.environ.get("NATS_PASSWORD")
    # if not nats_user or not nats_password:
    #     raise ValueError("NATS_USER or NATS_PASSWORD environment variable is not set.")
    nc = NATS()
    await nc.connect(servers=server_urls, tls={"certfile": "/etc/nats/tls/tls.crt", "keyfile": "/etc/nats/tls/tls.key", "cafile": "/etc/nats/tls/ca.crt"})
    # await nc.connect(servers=server_urls, user=nats_user, password=nats_password)

    # Read the number of iterations from the environment variable
    loop_count = int(os.getenv("LOOP_COUNT", 10))

    # Subjects to send requests to
    subjects = ["math.numbers.add", "math.numbers.subtract", "math.numbers.multiply", "math.numbers.divide"]

    for i in range(loop_count):
        # Generate two random numbers between 1 and 100
        num1 = random.randint(1, 100)
        num2 = random.randint(1, 100)
        payload = {"first": num1, "second": num2}

        for subject in subjects:
            try:
                # Send a request and wait for a response
                response = await nc.request(subject, json.dumps(payload).encode('utf-8'), timeout=2)
                print(f"Request to {subject} with payload {payload} received response: {response.data.decode()}")
            except Exception as e:
                print(f"Error sending request to {subject}: {e}")

    # Close the NATS connection
    await nc.close()

if __name__ == "__main__":
    asyncio.run(main())