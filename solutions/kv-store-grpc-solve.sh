#!/bin/bash
set -e

pip install grpcio==1.73.0 grpcio-tools==1.73.0

# Create proto file
cat > /app/kv-store.proto << 'EOF'
syntax = "proto3";

package kvstore;

service KVStore {
  rpc GetVal (GetValRequest) returns (GetValResponse);
  rpc SetVal (SetValRequest) returns (SetValResponse);
}

message GetValRequest {
  string key = 1;
}

message GetValResponse {
  int64 val = 1;
}

message SetValRequest {
  string key = 1;
  int64 value = 2;
}

message SetValResponse {
  int64 val = 1;
}
EOF

# Generate Python bindings
cd /app
python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. kv-store.proto

# Verify generated files exist
ls -la /app/kv_store_pb2.py /app/kv_store_pb2_grpc.py

# Create server
cat > /app/server.py << 'PYEOF'
import sys
sys.path.insert(0, "/app")

from concurrent import futures
import grpc
import kv_store_pb2
import kv_store_pb2_grpc


class Server(kv_store_pb2_grpc.KVStoreServicer):
    def __init__(self):
        self.store = {}

    def GetVal(self, request, context):
        val = self.store.get(request.key, 0)
        return kv_store_pb2.GetValResponse(val=val)

    def SetVal(self, request, context):
        self.store[request.key] = request.value
        return kv_store_pb2.SetValResponse(val=request.value)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    kv_store_pb2_grpc.add_KVStoreServicer_to_server(Server(), server)
    server.add_insecure_port("[::]:5328")
    server.start()
    print("Server started on port 5328")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
PYEOF

# Start server in background
nohup python3 /app/server.py > /tmp/server.log 2>&1 &
sleep 2

# Verify it's running
ss -tlnp | grep 5328 || netstat -tlnp | grep 5328 || echo "Checking port..."
echo "Server started!"
