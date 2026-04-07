NUM_TERMS = 1000

def compute_pi() -> float:
    total = 0.0
    for k in range(NUM_TERMS):
        total += (-1) ** k / (2 * k + 1)
    return 4 * total

if __name__ == "__main__":
    pi = compute_pi()
    print(pi)
