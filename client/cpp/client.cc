#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>

#include <grpcpp/grpcpp.h>

#include "add.grpc.pb.h"

namespace {

bool env_truthy(const char* v, const char* default_value) {
  const char* raw = std::getenv(v);
  std::string s = raw ? raw : default_value;
  for (auto& c : s) c = static_cast<char>(std::tolower(c));
  return (s == "1" || s == "true" || s == "yes" || s == "on");
}

std::string env_str(const char* v, const std::string& default_value) {
  const char* raw = std::getenv(v);
  return raw ? std::string(raw) : default_value;
}

std::string read_file(const std::string& path) {
  std::ifstream in(path, std::ios::in | std::ios::binary);
  if (!in) {
    throw std::runtime_error("Failed to open file: " + path);
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

std::shared_ptr<grpc::ChannelCredentials> make_channel_creds() {
  const bool tls_enabled = env_truthy("GRPC_TLS", "1");
  if (!tls_enabled) {
    return grpc::InsecureChannelCredentials();
  }

  const bool mtls_enabled = env_truthy("GRPC_MTLS", "0");

  const std::string default_root = mtls_enabled ? "certs/ca.crt" : "certs/server.crt";
  const std::string root_cert_path = env_str("GRPC_ROOT_CERT", default_root);

  grpc::SslCredentialsOptions opts;
  opts.pem_root_certs = read_file(root_cert_path);

  if (mtls_enabled) {
    const std::string client_cert_path = env_str("GRPC_CLIENT_CERT", "certs/client.crt");
    const std::string client_key_path = env_str("GRPC_CLIENT_KEY", "certs/client.key");

    opts.pem_cert_chain = read_file(client_cert_path);
    opts.pem_private_key = read_file(client_key_path);
  }

  return grpc::SslCredentials(opts);
}

int prompt_int(const std::string& name) {
  while (true) {
    std::cout << "Enter integer " << name << ": ";
    std::string s;
    if (!std::getline(std::cin, s)) {
      throw std::runtime_error("Failed to read input");
    }
    try {
      size_t idx = 0;
      int v = std::stoi(s, &idx);
      if (idx != s.size()) {
        throw std::invalid_argument("trailing chars");
      }
      return v;
    } catch (...) {
      std::cout << "Invalid integer: " << s << std::endl;
    }
  }
}

}  // namespace

int main(int argc, char** argv) {
  (void)argc;
  (void)argv;

  std::string host = env_str("GRPC_HOST", "localhost");
  if (host == "127.0.0.1" || host == "::1") {
    host = "localhost";
  }
  const std::string port = env_str("GRPC_PORT", "50051");
  const std::string target = host + ":" + port;

  auto creds = make_channel_creds();
  auto channel = grpc::CreateChannel(target, creds);
  add::Adder::Stub stub(channel);

  const int a = prompt_int("a");
  const int b = prompt_int("b");

  add::AddRequest req;
  req.set_a(a);
  req.set_b(b);

  add::AddReply resp;
  grpc::ClientContext ctx;

  grpc::Status status = stub.Add(&ctx, req, &resp);
  if (!status.ok()) {
    std::cerr << "RPC failed: " << status.error_message() << " (code=" << status.error_code() << ")" << std::endl;
    return 1;
  }

  std::cout << resp.result() << std::endl;
  return 0;
}
