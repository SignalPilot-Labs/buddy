#!/bin/bash
set -e

mkdir -p /app

cat > /app/parallel_linear.py << 'EOF'
import torch
import torch.nn as nn
import torch.distributed as dist


class ColumnParallelLinear(nn.Module):
    """
    Linear layer with column parallelism.

    Splits the weight matrix along the output (column) dimension.
    Each rank holds weight[start:end, :] where start/end are determined by rank.
    The forward pass simulates all_gather by concatenating partial outputs.
    The bias is sharded along the output dimension as well.
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        bias: bool,
        master_weight: torch.Tensor,
    ) -> None:
        super().__init__()

        world_size = dist.get_world_size()
        rank = dist.get_rank()

        out_per_partition = out_features // world_size
        start_idx = rank * out_per_partition
        end_idx = start_idx + out_per_partition

        weight_slice = master_weight[start_idx:end_idx, :].clone().detach()
        self.weight = nn.Parameter(weight_slice)

        if bias:
            bias_slice = torch.zeros(out_per_partition)
            self.bias = nn.Parameter(bias_slice)
        else:
            self.bias = None

        self._world_size = world_size
        self._out_features = out_features

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        partial_output = torch.nn.functional.linear(x, self.weight, self.bias)

        gather_list = [torch.zeros_like(partial_output) for _ in range(self._world_size)]
        dist.all_gather(gather_list, partial_output)

        return torch.cat(gather_list, dim=-1)


class RowParallelLinear(nn.Module):
    """
    Linear layer with row parallelism.

    Splits the weight matrix along the input (row) dimension.
    Each rank holds weight[:, start:end] where start/end are determined by rank.
    The forward pass simulates all_reduce by summing partial outputs.
    The bias is not sharded — each rank holds the full bias.
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        bias: bool,
        master_weight: torch.Tensor,
    ) -> None:
        super().__init__()

        world_size = dist.get_world_size()
        rank = dist.get_rank()

        in_per_partition = in_features // world_size
        start_idx = rank * in_per_partition
        end_idx = start_idx + in_per_partition

        weight_slice = master_weight[:, start_idx:end_idx].clone().detach()
        self.weight = nn.Parameter(weight_slice)

        if bias:
            self.bias = nn.Parameter(torch.zeros(out_features))
        else:
            self.bias = None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        partial_output = torch.nn.functional.linear(x, self.weight)

        dist.all_reduce(partial_output, op=dist.ReduceOp.SUM)

        if self.bias is not None:
            return partial_output + self.bias
        return partial_output
EOF

echo "Created /app/parallel_linear.py successfully"
