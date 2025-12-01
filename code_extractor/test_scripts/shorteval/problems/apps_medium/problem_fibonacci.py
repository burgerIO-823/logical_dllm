"""
APPS-Medium: Fibonacci with Memoization
Calculate the nth Fibonacci number using dynamic programming with memoization.
This is a classic medium-difficulty problem that demonstrates recursion,
caching, and algorithmic optimization.
"""

def fibonacci_memo(n: int, memo: dict = None) -> int:
    """
    Calculate the nth Fibonacci number using memoization.

    Args:
        n: The position in Fibonacci sequence (0-indexed)
        memo: Dictionary to cache computed values

    Returns:
        The nth Fibonacci number

    >>> fibonacci_memo(0)
    0
    >>> fibonacci_memo(1)
    1
    >>> fibonacci_memo(10)
    55
    >>> fibonacci_memo(20)
    6765
    """
    if memo is None:
        memo = {}

    if n in memo:
        return memo[n]

    if n <= 1:
        return n

    memo[n] = fibonacci_memo(n - 1, memo) + fibonacci_memo(n - 2, memo)
    return memo[n]


def fibonacci_iterative(n: int) -> int:
    """
    Calculate the nth Fibonacci number using iterative approach.
    More efficient than recursion for large n.
    """
    if n <= 1:
        return n

    prev, curr = 0, 1

    for i in range(2, n + 1):
        prev, curr = curr, prev + curr

    return curr


# Test execution
if __name__ == "__main__":
    print("Testing Fibonacci (Memoization):")
    for i in [0, 1, 5, 10, 15, 20]:
        result = fibonacci_memo(i)
        print(f"  fib({i}) = {result}")

    print("\nTesting Fibonacci (Iterative):")
    for i in [0, 1, 5, 10, 15, 20]:
        result = fibonacci_iterative(i)
        print(f"  fib({i}) = {result}")

    # Verify both methods give same results
    print("\nVerification:")
    for i in range(21):
        memo_result = fibonacci_memo(i)
        iter_result = fibonacci_iterative(i)
        match = "✓" if memo_result == iter_result else "✗"
        print(f"  n={i}: memo={memo_result}, iter={iter_result} {match}")
