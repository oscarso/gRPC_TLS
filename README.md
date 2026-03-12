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

## Run the server

```bash
python3 server/server.py
```

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
