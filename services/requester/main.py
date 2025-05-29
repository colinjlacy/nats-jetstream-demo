import os
import json
import asyncio
import random
import ssl
from nats.aio.client import Client as NATS

async def main():
    # Connect to the NATS cluster
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
    nc = NATS()
    await nc.connect(servers=server_urls, tls=ssl_ctx)

    # Read the number of iterations from the environment variable
    loop_count = int(os.getenv("LOOP_COUNT", 10))

    # Subjects to send requests to
    subjects = ["math.numbers.add", "math.numbers.subtract", "math.numbers.multiply", "math.numbers.divide"]

    for i in range(loop_count):
        # Generate two random numbers between 1 and 100
        num1 = random.randint(1, 100)
        num2 = random.randint(1, 100)

        for subject in subjects:
            try:
                payload = {"first": num1, "second": num2, "operation": subject.split(".")[-1]}
                # Send a request and wait for a response
                response = await nc.request(subject, json.dumps(payload).encode('utf-8'), timeout=2)
                answer = json.loads(response.data.decode())
                print(f"Request to {subject} with payload {payload} received response: {response.data.decode()}")
                if answer.get("result") is not None:
                    result = answer["result"]
                    # result is significant if greater than 1
                    # result is throwaway if less than or equal to 1
                    try:
                        if result > 1:
                            print(f"Result is significant: {result}")
                            await nc.publish("answers.significant", json.dumps(answer).encode('utf-8'), None, {"Nats-Msg-Id": f"{subject}-response-{i}"})
                            if os.environ.get("DUPLICATE", "false") == "true":
                                await asyncio.sleep(1)  # Simulate a delay for duplicate processing
                                await nc.publish("answers.significant", json.dumps(answer).encode('utf-8'), None, {"Nats-Msg-Id": f"{subject}-response-{i}"})
                        else:
                            print(f"Result is not significant: {result}")
                            await nc.publish("answers.throwaway", json.dumps(answer).encode('utf-8'), None, {"Nats-Msg-Id": f"{subject}-response-{i}"})
                            if os.environ.get("DUPLICATE", "false") == "true":
                                await asyncio.sleep(1)
                                await nc.publish("answers.significant", json.dumps(answer).encode('utf-8'), None, {"Nats-Msg-Id": f"{subject}-response-{i}"})
                    except Exception as e:
                        print(f"Error publishing result message: {e}")
            except Exception as e:
                print(f"Error sending request to {subject}: {e}")

    # Close the NATS connection
    await nc.close()

if __name__ == "__main__":
    asyncio.run(main())