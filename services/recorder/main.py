import asyncio
import json
import os
import signal
import ssl
from nats.aio.client import Client as NATS
import mysql.connector

# Read configuration from environment
NATS_SERVER = os.getenv("NATS_SERVER", "nats://localhost:4222")
NATS_SUBJECT = os.getenv("NATS_SUBJECT", "work.queue")
NATS_STREAM = os.getenv("NATS_STREAM", "work")
NATS_CONSUMER = os.getenv("NATS_CONSUMER", "work-consumer")

POD_ID = os.getenv("POD_ID", "unknown-pod")

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "workdb")


# Graceful shutdown
stop_event = asyncio.Event()
def shutdown():
    stop_event.set()


async def handle_message(msg):
    try:
        payload = json.loads(msg.data.decode())
        first = int(payload["first"])
        second = int(payload["second"])
        operation = str(payload["operation"])
        result = str(payload["result"])

        # Insert into MySQL
        cursor = db_conn.cursor()
        cursor.execute(
            """
            INSERT INTO operations (pod_id, first, second, result, operation)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (POD_ID, first, second, result, operation)
        )
        db_conn.commit()
        cursor.close()

        await msg.ack()

    except Exception as e:
        print(f"Error processing message: {e}")
        await msg.nak()


async def subscribe_and_process(js, nc):
    long_running = os.getenv("LONG_RUNNING", "false").lower() == "true"

    if long_running:
        print("Long-running mode: subscribing to messages...")
        await js.subscribe(
            subject=NATS_SUBJECT,
            durable=NATS_CONSUMER,
            stream=NATS_STREAM,
            bind=True,
            cb=handle_message,
            manual_ack=True
        )

        await stop_event.wait()

        print("Shutting down...")
        await nc.drain()
        db_conn.close()


    else:
        print("Consuming available messages and then exiting...")
        sub = await js.subscribe(
            subject=NATS_SUBJECT,
            durable=NATS_CONSUMER,
            stream=NATS_STREAM,
            bind=True
        )

        msgs = await sub.messages(batch=10, timeout=2.0)
        for msg in msgs:
            await handle_message(msg)

        print("Shutting down...")
        await js.nc.drain()
        db_conn.close()



async def main():
    global db_conn
    db_conn = mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )

        # Create an SSLContext
    ssl_ctx = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH,
        cafile="tls.ca"
    )
    ssl_ctx.load_cert_chain(
        certfile="tls.crt",
        keyfile="tls.key"
    )

    nc = NATS()
    await nc.connect(servers=[NATS_SERVER], tls=ssl_ctx)
    js = nc.jetstream()

    await subscribe_and_process(js, nc)

    print(f"Worker running as {POD_ID}, listening on subject '{NATS_SUBJECT}'")
    await stop_event.wait()

    print("Shutting down...")
    await nc.drain()
    db_conn.close()


if __name__ == "__main__":
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: shutdown())
    asyncio.run(main())
