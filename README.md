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

> **Note — Python client and TPM keys:** `client/py/client.py` uses the `grpcio` pip package,
> which bundles **BoringSSL** internally and does **not** use the system or local OpenSSL.
> To use a TPM/HSM key (e.g. from SoftHSMv2 via the pkcs11 provider) for TLS in Python gRPC code,
> `grpcio` must be **rebuilt from source** against the local OpenSSL 3.5.5 with
> `GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1`. This task has **not** been done — the Python client
> currently reads cert/key files from disk and cannot access SoftHSMv2 keys.
> The **C++ client** (`client/cpp/client.cpp`) is the recommended path for HSM-backed TLS.

## Native C++ gRPC client

There is also a native client implementation at `client/cpp/client.cpp` that behaves like the Python client:
- prompts for `a` and `b`
- calls `Adder.Add(a,b)`
- prints the sum

### Build the C++ client

The C++ client is built against the **locally built gRPC 1.78.1 + OpenSSL 3.5.5** under
`client/tpm/grpc/install` and `client/tpm/ossl3/install`. See the
[gRPC 1.78.1 build section](#grpc-1781-built-against-openssl-355) for how to build those first.

Set path variables (run from repo root):

```bash
GRPC=$(pwd)/client/tpm/grpc/install
OSSL=$(pwd)/client/tpm/ossl3/install
```

1. Generate C++ protobuf + gRPC sources from `proto/add.proto` using the local `protoc`:

```bash
$GRPC/bin/protoc -I proto \
  --cpp_out=client/cpp \
  --grpc_out=client/cpp \
  --plugin=protoc-gen-grpc=$GRPC/bin/grpc_cpp_plugin \
  proto/add.proto
```

This will create:
- `client/cpp/add.pb.h`, `client/cpp/add.pb.cc`
- `client/cpp/add.grpc.pb.h`, `client/cpp/add.grpc.pb.cc`

2. Compile the client:

```bash
c++ -std=c++17 \
  -Iclient/cpp -I$GRPC/include -I$OSSL/include \
  client/cpp/client.cpp client/cpp/add.pb.cc client/cpp/add.grpc.pb.cc \
  -L$GRPC/lib -L$OSSL/lib64 \
  -Wl,--start-group \
  -lgrpc++ -lgrpc -lgpr -lprotobuf \
  -lupb -lupb_message_lib -lupb_base_lib -lupb_mem_lib -lupb_wire_lib \
  -lupb_mini_table_lib -lupb_mini_descriptor_lib -lupb_hash_lib \
  -laddress_sorting -lcares -lre2 -lz \
  -labsl_synchronization -labsl_strings -labsl_str_format_internal \
  -labsl_status -labsl_statusor \
  -labsl_cord -labsl_cord_internal -labsl_cordz_info \
  -labsl_cordz_functions -labsl_cordz_handle \
  -labsl_base -labsl_spinlock_wait -labsl_raw_logging_internal -labsl_log_severity \
  -labsl_time -labsl_time_zone -labsl_civil_time \
  -labsl_int128 -labsl_strings_internal -labsl_string_view \
  -labsl_throw_delegate -labsl_malloc_internal \
  -labsl_stacktrace -labsl_symbolize -labsl_debugging_internal \
  -labsl_demangle_internal -labsl_demangle_rust \
  -labsl_decode_rust_punycode -labsl_utf8_for_code_point \
  -labsl_graphcycles_internal -labsl_kernel_timeout_internal \
  -labsl_hash -labsl_city -labsl_low_level_hash \
  -labsl_raw_hash_set -labsl_hashtablez_sampler \
  -labsl_random_distributions -labsl_random_seed_sequences \
  -labsl_random_internal_entropy_pool -labsl_random_internal_randen \
  -labsl_random_internal_randen_hwaes -labsl_random_internal_randen_hwaes_impl \
  -labsl_random_internal_randen_slow -labsl_random_internal_platform \
  -labsl_random_internal_seed_material -labsl_random_seed_gen_exception \
  -labsl_log_internal_check_op -labsl_log_internal_conditions \
  -labsl_log_internal_message -labsl_examine_stack \
  -labsl_log_internal_format -labsl_log_internal_nullguard \
  -labsl_log_internal_log_sink_set -labsl_log_internal_globals \
  -labsl_log_sink -labsl_log_globals -labsl_vlog_config_internal \
  -labsl_log_internal_fnmatch -labsl_strerror -labsl_leak_check \
  -labsl_exponential_biased -labsl_crc32c -labsl_crc_internal \
  -labsl_crc_cpu_detect -labsl_crc_cord_state -labsl_tracing_internal \
  -labsl_log_internal_structured_proto -labsl_log_internal_proto \
  -labsl_flags_internal -labsl_flags_reflection \
  -labsl_flags_private_handle_accessor \
  -labsl_flags_commandlineflag -labsl_flags_commandlineflag_internal \
  -labsl_flags_config -labsl_flags_program_name -labsl_flags_marshalling \
  -lutf8_range -lutf8_validity -lutf8_range_lib \
  -lssl -lcrypto -lpthread -ldl -lrt \
  -Wl,--end-group \
  -Wl,-rpath,$GRPC/lib -Wl,-rpath,$OSSL/lib64 \
  -o client/cpp/client_exe
```

Verify it links against local OpenSSL 3.5.5:

```bash
ldd client/cpp/client_exe | grep ssl
# libssl.so.3 => .../client/tpm/ossl3/install/lib64/libssl.so.3
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
Build OpenSSL 3.5.5 locally (installs to `client/tpm/ossl3/install/`).

> **Note:** The tarball (`openssl-3.5.5.tar.gz`) is listed in `.gitignore` and is **not committed to the repo** (it is ~51 MB). You must download it manually as shown below.

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

---

### 8. List all keys/objects on the token

Use `openssl storeutl` with a token-level PKCS#11 URI:

```bash
SOFTHSM2_CONF=client/tpm/softhsm2.conf \
LD_LIBRARY_PATH=client/tpm/ossl3/install/lib64 \
OPENSSL_CONF=client/tpm/ossl3/install/ssl/openssl.cnf \
  client/tpm/ossl3/install/bin/openssl storeutl \
  -provider pkcs11 -provider default \
  -noout -text \
  "pkcs11:token=mytoken?pin-value=1234"
```

Example output:
```
0: Public key
   PKCS11 EC Public Key (256 bits) — mykey (prime256v1)

1: Pkey
   PKCS11 EC Private Key (256 bits) — [not exportable]
   URI pkcs11:...;token=mytoken;id=%01;object=mykey;type=private

Total found: 2
```

Alternatively, use `pkcs11-tool` (simpler):

```bash
SOFTHSM2_CONF=client/tpm/softhsm2.conf \
  pkcs11-tool \
  --module client/tpm/install/lib/softhsm/libsofthsm2.so \
  --token-label mytoken --pin 1234 \
  --list-objects
```

## gRPC 1.78.1 (built against OpenSSL 3.5.5)

> **Status:**
> - ✅ **gRPC 1.78.1 C++ libraries** built and installed at `client/tpm/grpc/install/` against OpenSSL 3.5.5.
> - ✅ **`client/cpp/client_exe`** recompiled and verified to link against local OpenSSL 3.5.5.
> - ⏳ **`grpcio` (Python)** — rebuilding `grpcio` against OpenSSL 3.5.5 is **required** for any
>   Python gRPC code that wishes to access a TPM/HSM key via the pkcs11 provider. This has
>   **not yet been done**. It requires building `grpcio` from source with
>   `GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1 GRPC_PYTHON_BUILD_SYSTEM_ABSL=1` pointed at the local
>   OpenSSL 3.5.5 install.

The system gRPC 1.30.2 on Ubuntu 22.04 is linked against OpenSSL 3.0.2. To use the
pkcs11 provider (which requires OpenSSL ≥ 3.0.7), gRPC must be rebuilt against the
local OpenSSL 3.5.5 install.

### Directory layout

```
client/tpm/grpc/
  grpc-1.78.1/          # gRPC source + submodules (git clone)
  install/              # gRPC 1.78.1 install
    bin/
      grpc_cpp_plugin
      protoc
    lib/
      libgrpc.a
      libgrpc++.a
      pkgconfig/
        grpc.pc
        grpc++.pc
```

### Build dependencies

```bash
sudo apt install -y cmake build-essential git
```

### Clone with submodules

> **Note:** `client/tpm/grpc/grpc-1.78.1/` is listed in `.gitignore` — it must be cloned manually.

```bash
mkdir -p client/tpm/grpc
git clone --recurse-submodules -b v1.78.1 --depth 1 \
  https://github.com/grpc/grpc \
  client/tpm/grpc/grpc-1.78.1
```

### Configure against local OpenSSL 3.5.5

```bash
OSSL=$(pwd)/client/tpm/ossl3/install

cmake -S client/tpm/grpc/grpc-1.78.1 \
  -B client/tpm/grpc/grpc-1.78.1/cmake_build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=$(pwd)/client/tpm/grpc/install \
  -DCMAKE_PREFIX_PATH=$OSSL \
  -DOPENSSL_ROOT_DIR=$OSSL \
  -DOPENSSL_INCLUDE_DIR=$OSSL/include \
  -DOPENSSL_CRYPTO_LIBRARY=$OSSL/lib64/libcrypto.so \
  -DOPENSSL_SSL_LIBRARY=$OSSL/lib64/libssl.so \
  -DgRPC_SSL_PROVIDER=package \
  -DgRPC_BUILD_TESTS=OFF \
  -DgRPC_INSTALL=ON \
  -DCMAKE_EXE_LINKER_FLAGS="-Wl,-rpath,$OSSL/lib64" \
  -DCMAKE_SHARED_LINKER_FLAGS="-Wl,-rpath,$OSSL/lib64"
```

Verify OpenSSL 3.5.5 was picked up:
```
-- Found OpenSSL: .../client/tpm/ossl3/install/lib64/libcrypto.so (found version "3.5.5")
```

### Build and install

```bash
cmake --build client/tpm/grpc/grpc-1.78.1/cmake_build --parallel $(nproc)
cmake --install client/tpm/grpc/grpc-1.78.1/cmake_build
```

### Verify

```bash
PKG_CONFIG_PATH=client/tpm/grpc/install/lib/pkgconfig \
  pkg-config --modversion grpc++
# 1.78.1
```

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
