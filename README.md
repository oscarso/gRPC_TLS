# gRPC_TLS

This repository contains a simple Python **gRPC server** (with an `Add(a,b)` RPC) plus a **REST API** (`/add`) that forwards requests to the gRPC method, and a Python **gRPC client** that prompts for `a` and `b` and prints the sum.

## What the server does

- **gRPC server**
  - Listens on `localhost:50051` by default
  - Implements `Adder.Add(AddRequest{a,b}) -> AddReply{result}`
- **REST server (Flask)**
  - Listens on `localhost:5000` by default
  - Exposes `GET /add?a=<int>&b=<int>` and `POST /add` with JSON body `{"a": <int>, "b": <int>}`
  - Calls the gRPC `Add` method internally and returns JSON `{"result": <int>}`

The service definition is in `proto/add.proto`.

## What the client does

- Prompts you to enter two integers: `a` and `b`
- Connects to the gRPC server (`localhost:50051` by default)
- Calls `Adder.Add(a,b)`
- Prints the returned sum (`result`)

## Setup (Python virtual environment)

From the repository root:

1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

## TLS for gRPC (server <-> client)

The gRPC server and client are configured to use **TLS by default** (`GRPC_TLS=1`).

Important: this TLS setting applies to the **gRPC connection** on `localhost:50051`. The REST API is a separate Flask server and will still be served over **HTTP** (you will see `http://localhost:5000`), unless you separately enable HTTPS for Flask or run it behind a reverse proxy that terminates TLS.

### Generate a local dev certificate (self-signed)

From the repository root:

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/server.key \
  -out certs/server.crt \
  -days 365 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost"
```

This produces:
- `certs/server.key` (server private key)
- `certs/server.crt` (server certificate; also used as the client "root" cert for local dev)

### TLS-related environment variables

- `GRPC_TLS`
  - `1` (default) enables TLS
  - `0` disables TLS (insecure)
- `GRPC_SERVER_CERT` (server only)
  - default: `certs/server.crt`
- `GRPC_SERVER_KEY` (server only)
  - default: `certs/server.key`
- `GRPC_ROOT_CERT` (client and REST->gRPC)
  - default: `certs/server.crt`

## Run the server

```bash
python3 server/server.py
```

Note: the REST API is plain HTTP, but it forwards requests to the gRPC server using TLS (when `GRPC_TLS=1`).

### Debug logging (print every call)

To print every incoming REST request + response and every gRPC `Add` call (with inputs/outputs) to the console:

```bash
DEBUG_LOG=1 python3 server/server.py
```

Default ports:
- REST: `http://localhost:5000`
- gRPC: `localhost:50051`

### Call the REST API

GET:
```bash
curl "http://localhost:5000/add?a=2&b=3"
```

POST:
```bash
curl -X POST "http://localhost:5000/add" \
  -H "Content-Type: application/json" \
  -d '{"a":2,"b":3}'
```

## Run the client

In another terminal (with the same virtualenv activated):

```bash
python3 client/py/client.py
```

Optional flags:
```bash
python3 client/py/client.py --host localhost --port 50051
```

## Configuration

Environment variables supported by the server:
- `GRPC_HOST` (default `localhost`)
- `GRPC_PORT` (default `50051`)
- `REST_HOST` (default `localhost`)
- `REST_PORT` (default `5000`)

Environment variables supported by the client:
- `GRPC_HOST` (default `localhost`)
- `GRPC_PORT` (default `50051`)
