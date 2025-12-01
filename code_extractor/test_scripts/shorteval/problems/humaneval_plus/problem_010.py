"""
HumanEval++ #10: make_palindrome
Find the shortest palindrome that begins with a supplied string.
Algorithm idea is simple:
- Find the longest postfix of supplied string that is a palindrome.
- Append to the end of the string reverse of a string prefix that comes before the palindromic suffix.
"""

def is_palindrome(string: str) -> bool:
    """
    Test if given string is a palindrome.
    """
    return string == string[::-1]


def make_palindrome(string: str) -> str:
    """
    Find the shortest palindrome that begins with a supplied string.

    >>> make_palindrome('')
    ''
    >>> make_palindrome('cat')
    'catac'
    >>> make_palindrome('cata')
    'catac'
    """
    if not string:
        return ''

    beginning_of_suffix = 0

    while not is_palindrome(string[beginning_of_suffix:]):
        beginning_of_suffix += 1

    return string + string[:beginning_of_suffix][::-1]


# Test execution
if __name__ == "__main__":
    # Test cases
    test1 = make_palindrome('')
    print(f"Test 1 (empty): '{test1}'")

    test2 = make_palindrome('cat')
    print(f"Test 2 (cat): '{test2}'")

    test3 = make_palindrome('cata')
    print(f"Test 3 (cata): '{test3}'")

    test4 = make_palindrome('x')
    print(f"Test 4 (x): '{test4}'")

    test5 = make_palindrome('xyz')
    print(f"Test 5 (xyz): '{test5}'")
