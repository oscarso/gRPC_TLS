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

### Mutual TLS (mTLS)

Mutual TLS means **both sides authenticate**:
- the client verifies the server certificate
- the server also verifies a **client certificate**

Why `client.key` is needed: in mTLS the client must prove it **owns** the client certificate it presents. The private key (`client.key`) is used during the TLS handshake to provide proof-of-possession (authentication). The certificate file (`client.crt`) alone is not enough.

To enable mTLS:

```bash
GRPC_MTLS=1 python3 server/server.py
```

In mTLS mode, this project expects:
- a local CA certificate at `certs/ca.crt`
- a server certificate/key at `certs/server.crt` + `certs/server.key` signed by that CA
- a client certificate/key at `certs/client.crt` + `certs/client.key` signed by that CA

#### Generate local dev CA + server cert + client cert

From the repository root:

```bash
mkdir -p certs

# 1) Create a local CA
openssl genrsa -out certs/ca.key 2048
openssl req -x509 -new -nodes -key certs/ca.key -sha256 -days 3650 \
  -out certs/ca.crt \
  -subj "/CN=Local Dev CA"

# 2) Server key + CSR
openssl genrsa -out certs/server.key 2048
openssl req -new -key certs/server.key -out certs/server.csr -subj "/CN=localhost"

# 3) Sign server CSR with CA (includes SAN=localhost)
openssl x509 -req -in certs/server.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
  -out certs/server.crt -days 365 -sha256 \
  -extfile <(printf "subjectAltName=DNS:localhost")

# 4) Client key + CSR
openssl genrsa -out certs/client.key 2048
openssl req -new -key certs/client.key -out certs/client.csr -subj "/CN=grpc-client"

# 5) Sign client CSR with CA
openssl x509 -req -in certs/client.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
  -out certs/client.crt -days 365 -sha256
```

Note: the `extfile <(...)` syntax uses process substitution (works in `zsh`).

After running the commands above, your `certs/` folder should contain (at minimum):

- **CA (used to sign and to verify)**
  - `certs/ca.crt`
  - `certs/ca.key`
- **Server identity (presented by gRPC server)**
  - `certs/server.crt`
  - `certs/server.key`
- **Client identity (presented by gRPC client)**
  - `certs/client.crt`
  - `certs/client.key`

It will also contain intermediate artifacts created during signing:

- `certs/server.csr`
- `certs/client.csr`
- `certs/ca.srl`

#### mTLS-related environment variables

- `GRPC_MTLS`
  - `1` enables mTLS (default `0`)
- `GRPC_CLIENT_CA_CERT` (server)
  - CA certificate used by the server to verify client certs
  - default: `certs/ca.crt`
- `GRPC_ROOT_CERT` (client and REST->gRPC)
  - CA certificate used by the client to verify the server cert
  - default when `GRPC_MTLS=1`: `certs/ca.crt`
- `GRPC_CLIENT_CERT` (client and REST->gRPC)
  - default: `certs/client.crt`
- `GRPC_CLIENT_KEY` (client and REST->gRPC)
  - default: `certs/client.key`

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

## Native C++ gRPC client

There is also a native client implementation at `client/cpp/client.cpp` that behaves like the Python client:
- prompts for `a` and `b`
- calls `Adder.Add(a,b)`
- prints the sum

### Build the C++ client

You need `protoc`, the gRPC C++ plugin, and the gRPC/protobuf libraries available on your system.

1. Generate C++ protobuf + gRPC sources from `proto/add.proto`:

```bash
protoc -I proto \
  --cpp_out=client/cpp \
  --grpc_out=client/cpp \
  --plugin=protoc-gen-grpc=$(which grpc_cpp_plugin) \
  proto/add.proto
```

This will create:
- `client/cpp/add.pb.h`, `client/cpp/add.pb.cc`
- `client/cpp/add.grpc.pb.h`, `client/cpp/add.grpc.pb.cc`

2. Compile the client:

```bash
c++ -std=c++17 \
  -Iclient/cpp \
  client/cpp/client.cpp client/cpp/add.pb.cc client/cpp/add.grpc.pb.cc \
  $(pkg-config --cflags --libs grpc++ protobuf) \
  -o client/cpp/client_exe
```

### Run the C++ client

```bash
GRPC_HOST=localhost ./client/cpp/client_exe
```

TLS and mTLS are controlled by the same environment variables described above (`GRPC_TLS`, `GRPC_MTLS`, `GRPC_ROOT_CERT`, `GRPC_CLIENT_CERT`, `GRPC_CLIENT_KEY`, etc.).

## Configuration

Environment variables supported by the server:
- `GRPC_HOST` (default `localhost`)
- `GRPC_PORT` (default `50051`)
- `REST_HOST` (default `localhost`)
- `REST_PORT` (default `5000`)

Environment variables supported by the client:
- `GRPC_HOST` (default `localhost`)
- `GRPC_PORT` (default `50051`)
