"""
HumanEval #1: separate_paren_groups
Input to this function is a string containing multiple groups of nested parentheses.
Your goal is to separate those groups into separate strings and return the list of those.
"""

from typing import List


def separate_paren_groups(paren_string: str) -> List[str]:
    """
    Separate groups of nested parentheses into separate strings.

    >>> separate_paren_groups('( ) (( )) (( )( ))')
    ['()', '(())', '(()())']
    """
    result = []
    current_string = []
    current_depth = 0

    for c in paren_string:
        if c == '(':
            current_depth += 1
            current_string.append(c)
        elif c == ')':
            current_depth -= 1
            current_string.append(c)

            if current_depth == 0:
                result.append(''.join(current_string))
                current_string = []

    return result


# Test execution
if __name__ == "__main__":
    # Basic test cases
    test1 = separate_paren_groups('( ) (( )) (( )( ))')
    print(f"Test 1: {test1}")

    test2 = separate_paren_groups('() (()) (()())')
    print(f"Test 2: {test2}")

    test3 = separate_paren_groups('((()))')
    print(f"Test 3: {test3}")
