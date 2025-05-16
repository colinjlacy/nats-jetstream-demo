import asyncio
import json
import os
import signal
import ssl
from nats.aio.client import Client as NATS
import mysql.connector

# Read configuration from environment
NATS_SERVER = os.getenv("NATS_SERVER",
                        "nats://k8s-default-natseast-d3a2cc2411-682b3011270d1d56.elb.us-east-1.amazonaws.com:4222")
NATS_SUBJECT = os.getenv("NATS_SUBJECT", "answers.throwaway")
NATS_STREAM = os.getenv("NATS_STREAM", "answers")
NATS_CONSUMER = os.getenv("NATS_CONSUMER", "answers-consumer")
NATS_TLS_PATH = os.getenv("NATS_TLS_PATH", "./")

POD_ID = os.getenv("POD_ID", "local")

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "answers")
MYSQL_TABLE = os.getenv("MYSQL_TABLE", "throwaway")

# Graceful shutdown
stop_event = asyncio.Event()


def shutdown():
    stop_event.set()


async def fetch_messages(sub):
    try:
        msgs = await sub.fetch(timeout=5)
        while msgs:
            for msg in msgs:
                print(f"Received message: {msg.data.decode()}")
                await handle_message(msg)
                msgs = await sub.fetch(timeout=5)
    except asyncio.TimeoutError:
        print("Timeout reached, resetting fetch...")
        await fetch_messages(sub)


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
            f"""
            INSERT INTO {MYSQL_TABLE} (pod_id, first, second, result, operation)
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
        sub = await js.pull_subscribe(
            subject=NATS_SUBJECT,
            durable=NATS_CONSUMER,
            stream=NATS_STREAM,
        )

        try:
            await fetch_messages(sub)
        except Exception as e:
            print(f"Error during message processing: {e}")
            db_conn.close()
            asyncio.get_event_loop().stop()
        finally:
            print("Cleaning up...")
            await sub.unsubscribe()

        print("Shutting down...")
        await nc.drain()
        db_conn.close()

    else:
        print("Consuming available messages and then exiting...")
        sub = await js.pull_subscribe(
            subject=NATS_SUBJECT,
            stream=NATS_STREAM,
        )

        # cinfo = await js.add_consumer(
        #     stream=NATS_STREAM,
        #     filter_subjects=["answers.*"],
        #     inactive_threshold=300.0,
        # )
        #
        # # Using named arguments.
        # sub = await js.pull_subscribe_bind(
        #     stream=NATS_STREAM, consumer=cinfo.name
        # )

        try:
            msgs = await sub.fetch(timeout=5)
            while msgs:
                for msg in msgs:
                    print(f"Received message: {msg.data.decode()}")
                    await handle_message(msg)
                    msgs = await sub.fetch(timeout=5)
        except asyncio.TimeoutError:
            print("No more messages. Shutting down...")
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

    print(f"checking the TLS path: {NATS_TLS_PATH}")
    if not os.path.exists(NATS_TLS_PATH):
        print(f"TLS path does not exist: {NATS_TLS_PATH}")
        return
    print(f"{NATS_TLS_PATH}/ca.crt")

    # Create an SSLContext
    ssl_ctx = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH,
        cafile=f"{NATS_TLS_PATH}/ca.crt"
    )
    ssl_ctx.load_cert_chain(
        certfile=f"{NATS_TLS_PATH}/tls.crt",
        keyfile=f"{NATS_TLS_PATH}/tls.key"
    )

    nc = NATS()
    await nc.connect(servers=[NATS_SERVER], tls=ssl_ctx)
    js = nc.jetstream()

    print(f"Worker running as {POD_ID}, listening on subject '{NATS_SUBJECT}'")
    await subscribe_and_process(js, nc)


if __name__ == "__main__":
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: shutdown())
    asyncio.run(main())
