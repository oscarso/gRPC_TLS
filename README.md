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

You need the following tools and libraries installed:

- **`protoc`** — Protocol Buffers compiler
- **`grpc_cpp_plugin`** — gRPC C++ protoc plugin
- **gRPC/protobuf C++ libraries** — headers and `.pc` files consumed by `pkg-config`

On Ubuntu/Debian, install with:

```bash
sudo apt install -y protobuf-compiler protobuf-compiler-grpc libgrpc++-dev libgrpc-dev libprotobuf-dev
```

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

Start the server first (from the repo root). With TLS (default):

```bash
python3 server/server.py
```

With mTLS:

```bash
GRPC_MTLS=1 python3 server/server.py
```

Then run the client. With TLS (default):

```bash
GRPC_HOST=localhost ./client/cpp/client_exe
```

With mTLS (from the repo root):

```bash
GRPC_MTLS=1 ./client/cpp/client_exe
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

## SoftHSMv2 + OpenSSL 3.5.5 + pkcs11-provider (PKCS#11 via OpenSSL provider)

`client/tpm/` contains local builds of SoftHSMv2, OpenSSL 3.5.5, and pkcs11-provider,
enabling P-256 key generation and access via the OpenSSL 3 provider API (no engine).

### Directory layout

```
client/tpm/
  install/                        # SoftHSMv2 2.7.0 install
    bin/softhsm2-util
    lib/softhsm/libsofthsm2.so    # PKCS#11 shared library
  ossl3/
    openssl-3.5.5/                # OpenSSL 3.5.5 source
    install/                      # OpenSSL 3.5.5 install
      bin/openssl
      lib64/
        libcrypto.so.3
        libssl.so.3
        ossl-modules/
          pkcs11.so               # pkcs11-provider 1.2.0
      ssl/openssl.cnf             # configured to load pkcs11 provider
  p11prov/
    pkcs11-provider-main/         # pkcs11-provider source (main branch)
    install/
  softhsm2.conf                   # SoftHSM config (tokendir = client/tpm/tokens/)
  tokens/                         # initialised token storage
```

---

### 1. Build SoftHSMv2 2.7.0

Install build dependencies:

```bash
sudo apt install -y libssl-dev automake autoconf libtool
```

Download and build (installs to `client/tpm/install/`):

```bash
mkdir -p client/tpm
curl -L https://api.github.com/repos/softhsm/SoftHSMv2/tarball/2.7.0 \
  -o client/tpm/SoftHSMv2-2.7.0.tar.gz
tar -xzf client/tpm/SoftHSMv2-2.7.0.tar.gz -C client/tpm/
cd client/tpm/softhsm-SoftHSMv2-*
sh autogen.sh
./configure --prefix=$(pwd)/../install
make -j$(nproc)
make install
```

---

### 2. Build OpenSSL 3.5.5

Ubuntu 22.04 ships OpenSSL 3.0.2 which is too old for pkcs11-provider (requires ≥ 3.0.7).
Build OpenSSL 3.5.5 locally (installs to `client/tpm/ossl3/install/`):

```bash
mkdir -p client/tpm/ossl3
curl -L https://github.com/openssl/openssl/releases/download/openssl-3.5.5/openssl-3.5.5.tar.gz \
  -o client/tpm/ossl3/openssl-3.5.5.tar.gz
tar -xzf client/tpm/ossl3/openssl-3.5.5.tar.gz -C client/tpm/ossl3/
cd client/tpm/ossl3/openssl-3.5.5
./config --prefix=$(pwd)/../install --openssldir=$(pwd)/../install/ssl
make -j$(nproc)
make install
```

Verify:

```bash
LD_LIBRARY_PATH=client/tpm/ossl3/install/lib64 \
  client/tpm/ossl3/install/bin/openssl version
# OpenSSL 3.5.5 27 Jan 2026
```

---

### 3. Build pkcs11-provider 1.2.0

Install build dependencies:

```bash
sudo apt install -y meson libp11-kit-dev pkg-config
```

Download and build against local OpenSSL 3.5.5:

```bash
mkdir -p client/tpm/p11prov
curl -L https://github.com/latchset/pkcs11-provider/archive/refs/heads/main.tar.gz \
  -o client/tpm/p11prov/pkcs11-provider-main.tar.gz
tar -xzf client/tpm/p11prov/pkcs11-provider-main.tar.gz -C client/tpm/p11prov/
cd client/tpm/p11prov/pkcs11-provider-main
PKG_CONFIG_PATH=$(pwd)/../../ossl3/install/lib64/pkgconfig \
  meson setup builddir --prefix=$(pwd)/../install
meson compile -C builddir
meson install -C builddir
```

`pkcs11.so` is installed directly into OpenSSL's modules directory:
`client/tpm/ossl3/install/lib64/ossl-modules/pkcs11.so`

---

### 4. Configure OpenSSL to load the pkcs11 provider

Edit `client/tpm/ossl3/install/ssl/openssl.cnf` — add `pkcs11` to `[provider_sect]`
and add `[pkcs11_sect]` pointing at `libsofthsm2.so`:

```ini
[provider_sect]
default = default_sect
pkcs11 = pkcs11_sect

[default_sect]
activate = 1

[pkcs11_sect]
module = /path/to/client/tpm/ossl3/install/lib64/ossl-modules/pkcs11.so
pkcs11-module-path = /path/to/client/tpm/install/lib/softhsm/libsofthsm2.so
activate = 1
```

Verify both providers load:

```bash
LD_LIBRARY_PATH=client/tpm/ossl3/install/lib64 \
OPENSSL_CONF=client/tpm/ossl3/install/ssl/openssl.cnf \
  client/tpm/ossl3/install/bin/openssl list -providers
# Providers:
#   default   (OpenSSL Default Provider 3.5.5) active
#   pkcs11    (PKCS#11 Provider 1.2.0)         active
```

---

### 5. Initialise a SoftHSMv2 token

```bash
mkdir -p client/tpm/tokens
cat > client/tpm/softhsm2.conf <<EOF
directories.tokendir = $(pwd)/client/tpm/tokens
objectstore.backend = file
EOF

SOFTHSM2_CONF=client/tpm/softhsm2.conf \
  client/tpm/install/bin/softhsm2-util \
  --init-token --free \
  --label "mytoken" \
  --pin 1234 --so-pin 12345678
```

---

### 6. Generate a P-256 (EC) key on the token

Uses `pkcs11-tool` from the `opensc` package:

```bash
sudo apt install -y opensc

SOFTHSM2_CONF=client/tpm/softhsm2.conf \
  pkcs11-tool \
  --module client/tpm/install/lib/softhsm/libsofthsm2.so \
  --token-label mytoken --pin 1234 \
  --keypairgen --key-type EC:prime256v1 \
  --label mykey --id 01
```

---

### 7. Access the key via OpenSSL pkcs11 provider

Export the public key using a PKCS#11 URI (no engine):

```bash
SOFTHSM2_CONF=client/tpm/softhsm2.conf \
LD_LIBRARY_PATH=client/tpm/ossl3/install/lib64 \
OPENSSL_CONF=client/tpm/ossl3/install/ssl/openssl.cnf \
  client/tpm/ossl3/install/bin/openssl pkey \
  -provider pkcs11 -provider default \
  -in "pkcs11:token=mytoken;object=mykey;type=private?pin-value=1234" \
  -pubout -text
```

> **Note:** Always run from the repo root so relative paths in `softhsm2.conf` resolve correctly.
> Use absolute paths in `openssl.cnf` for `module` and `pkcs11-module-path`.

## Pushing to GitHub

GitHub no longer accepts passwords for HTTPS `git push`. Use a **Personal Access Token (PAT)** instead.

### Generate a classic token

1. Go to https://github.com/settings/tokens → **Generate new token (classic)**
2. Select scope: `repo`
3. Copy the token

### Store the token (one-time setup)

```bash
git config --global credential.helper store
```

Then push — when prompted, enter your GitHub username and paste the token as the password:

```bash
git push
# Username: oscarso
# Password: <paste your classic token here>
```

The token is saved to `~/.git-credentials` and you will not be prompted again.
