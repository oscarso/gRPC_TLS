import argparse
import os

import grpc


def _maybe_generate_grpc_stubs() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    proto_path = os.path.join(repo_root, "proto", "add.proto")
    if not os.path.exists(proto_path):
        raise FileNotFoundError(f"Missing proto file: {proto_path}")

    out_dir = os.path.abspath(os.path.dirname(__file__))
    pb2_path = os.path.join(out_dir, "add_pb2.py")
    pb2_grpc_path = os.path.join(out_dir, "add_pb2_grpc.py")
    if os.path.exists(pb2_path) and os.path.exists(pb2_grpc_path):
        return

    try:
        from grpc_tools import protoc
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "gRPC stubs are missing and grpcio-tools is not installed. "
            "Install dependencies (pip install -r requirements.txt) or generate stubs via: "
            "python3 -m grpc_tools.protoc -I proto --python_out=client/py --grpc_python_out=client/py proto/add.proto"
        ) from e

    args = [
        "protoc",
        f"-I{os.path.join(repo_root, 'proto')}",
        f"--python_out={out_dir}",
        f"--grpc_python_out={out_dir}",
        proto_path,
    ]
    rc = protoc.main(args)
    if rc != 0:
        raise RuntimeError(f"protoc failed with exit code {rc}")


def _tls_enabled() -> bool:
    return os.environ.get("GRPC_TLS", "1").strip().lower() in {"1", "true", "yes", "on"}


def _read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _grpc_channel_credentials() -> grpc.ChannelCredentials:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    root_cert_path = os.environ.get(
        "GRPC_ROOT_CERT",
        os.path.abspath(os.path.join(repo_root, "certs", "server.crt")),
    )
    if not os.path.exists(root_cert_path):
        raise FileNotFoundError(
            "TLS is enabled but root certificate is missing. "
            f"Expected GRPC_ROOT_CERT={root_cert_path}"
        )
    root_certs = _read_file_bytes(root_cert_path)
    return grpc.ssl_channel_credentials(root_certificates=root_certs)


def _prompt_int(name: str) -> int:
    while True:
        raw = input(f"Enter integer {name}: ").strip()
        try:
            return int(raw)
        except ValueError:
            print(f"Invalid integer: {raw}")


def main() -> None:
    parser = argparse.ArgumentParser(description="gRPC client for Adder.Add")
    parser.add_argument("--host", default=os.environ.get("GRPC_HOST", "localhost"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("GRPC_PORT", "50051")),
    )
    args = parser.parse_args()

    _maybe_generate_grpc_stubs()

    import add_pb2  # noqa: E402
    import add_pb2_grpc  # noqa: E402

    a = _prompt_int("a")
    b = _prompt_int("b")

    target = f"{args.host}:{args.port}"

    if _tls_enabled():
        creds = _grpc_channel_credentials()
        channel = grpc.secure_channel(target, creds)
    else:
        channel = grpc.insecure_channel(target)

    with channel:
        stub = add_pb2_grpc.AdderStub(channel)
        reply = stub.Add(add_pb2.AddRequest(a=a, b=b))

    print(reply.result)


if __name__ == "__main__":
    main()
