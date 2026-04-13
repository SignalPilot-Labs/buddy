def test_hello_world():
    with open("/app/hello.txt", "r") as f:
        content = f.read()
    assert content == "hello world", f"Expected 'hello world', got {content!r}"
