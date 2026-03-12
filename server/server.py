import os
import sys
import logging
import threading
from concurrent import futures

import grpc
from flask import Flask, jsonify, request


def _maybe_generate_grpc_stubs() -> None:
    proto_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "proto", "add.proto")
    )
    if not os.path.exists(proto_path):
        raise FileNotFoundError(f"Missing proto file: {proto_path}")

    server_dir = os.path.abspath(os.path.dirname(__file__))
    pb2_path = os.path.join(server_dir, "add_pb2.py")
    pb2_grpc_path = os.path.join(server_dir, "add_pb2_grpc.py")
    if os.path.exists(pb2_path) and os.path.exists(pb2_grpc_path):
        return

    try:
        from grpc_tools import protoc
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "gRPC stubs are missing and grpcio-tools is not installed. "
            "Install dependencies (pip install -r requirements.txt) or generate stubs via: "
            "python3 -m grpc_tools.protoc -I proto --python_out=server --grpc_python_out=server proto/add.proto"
        ) from e

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    args = [
        "protoc",
        f"-I{os.path.join(repo_root, 'proto')}",
        f"--python_out={server_dir}",
        f"--grpc_python_out={server_dir}",
        proto_path,
    ]
    rc = protoc.main(args)
    if rc != 0:
        raise RuntimeError(f"protoc failed with exit code {rc}")


_maybe_generate_grpc_stubs()

import add_pb2  # noqa: E402
import add_pb2_grpc  # noqa: E402


def _debug_enabled() -> bool:
    return os.environ.get("DEBUG_LOG", "").strip().lower() in {"1", "true", "yes", "on"}


def _tls_enabled() -> bool:
    return os.environ.get("GRPC_TLS", "1").strip().lower() in {"1", "true", "yes", "on"}


def _read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _grpc_server_credentials() -> grpc.ServerCredentials:
    cert_path = os.environ.get(
        "GRPC_SERVER_CERT",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "certs", "server.crt")),
    )
    key_path = os.environ.get(
        "GRPC_SERVER_KEY",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "certs", "server.key")),
    )

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        raise FileNotFoundError(
            "TLS is enabled but server certificate/key files are missing. "
            f"Expected GRPC_SERVER_CERT={cert_path} and GRPC_SERVER_KEY={key_path}"
        )

    private_key = _read_file_bytes(key_path)
    certificate_chain = _read_file_bytes(cert_path)
    return grpc.ssl_server_credentials(((private_key, certificate_chain),))


def _grpc_channel_credentials() -> grpc.ChannelCredentials:
    root_cert_path = os.environ.get(
        "GRPC_ROOT_CERT",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "certs", "server.crt")),
    )
    if not os.path.exists(root_cert_path):
        raise FileNotFoundError(
            "TLS is enabled but root certificate is missing. "
            f"Expected GRPC_ROOT_CERT={root_cert_path}"
        )
    root_certs = _read_file_bytes(root_cert_path)
    return grpc.ssl_channel_credentials(root_certificates=root_certs)


_logger = logging.getLogger("grpc_tls")
if _debug_enabled():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class Adder(add_pb2_grpc.AdderServicer):
    def Add(self, request, context):
        a = int(request.a)
        b = int(request.b)
        result = a + b
        if _debug_enabled():
            _logger.info("gRPC Add called: a=%s b=%s -> result=%s", a, b, result)
        return add_pb2.AddReply(result=result)


def serve_grpc(host: str, port: int) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_pb2_grpc.add_AdderServicer_to_server(Adder(), server)
    if _tls_enabled():
        server.add_secure_port(f"{host}:{port}", _grpc_server_credentials())
    else:
        server.add_insecure_port(f"{host}:{port}")
    server.start()
    return server


def create_rest_app(grpc_host: str, grpc_port: int) -> Flask:
    app = Flask(__name__)

    if _debug_enabled():
        @app.before_request
        def _log_rest_incoming():
            payload = request.get_json(silent=True)
            _logger.info(
                "REST request: %s %s args=%s json=%s",
                request.method,
                request.path,
                dict(request.args),
                payload,
            )

        @app.after_request
        def _log_rest_outgoing(response):
            body = response.get_data(as_text=True)
            _logger.info(
                "REST response: %s %s status=%s body=%s",
                request.method,
                request.path,
                response.status,
                body,
            )
            return response

    @app.get("/add")
    @app.post("/add")
    def add_route():
        if request.method == "GET":
            a = request.args.get("a", type=int)
            b = request.args.get("b", type=int)
        else:
            payload = request.get_json(silent=True) or {}
            a = payload.get("a")
            b = payload.get("b")

        if a is None or b is None:
            return jsonify({"error": "Missing required integers a and b"}), 400

        try:
            a = int(a)
            b = int(b)
        except (TypeError, ValueError):
            return jsonify({"error": "a and b must be integers"}), 400

        if _tls_enabled():
            creds = _grpc_channel_credentials()
            channel = grpc.secure_channel(f"{grpc_host}:{grpc_port}", creds)
        else:
            channel = grpc.insecure_channel(f"{grpc_host}:{grpc_port}")

        with channel:
            stub = add_pb2_grpc.AdderStub(channel)
            reply = stub.Add(add_pb2.AddRequest(a=a, b=b))
        return jsonify({"result": int(reply.result)})

    return app


def main() -> None:
    grpc_host = os.environ.get("GRPC_HOST", "localhost")
    grpc_port = int(os.environ.get("GRPC_PORT", "50051"))
    rest_host = os.environ.get("REST_HOST", "localhost")
    rest_port = int(os.environ.get("REST_PORT", "5000"))

    grpc_server = serve_grpc(grpc_host, grpc_port)
    app = create_rest_app(grpc_host, grpc_port)

    rest_thread = threading.Thread(
        target=lambda: app.run(
            host=rest_host,
            port=rest_port,
            threaded=True,
            debug=_debug_enabled(),
            use_reloader=False,
        ),
        daemon=True,
    )
    rest_thread.start()

    try:
        grpc_server.wait_for_termination()
    except KeyboardInterrupt:
        grpc_server.stop(grace=2)


if __name__ == "__main__":
    main()
