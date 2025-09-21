extern printf(...) -> int;
extern malloc(int) -> void*;

fn main() -> int {
    var test: char* = malloc(1);
    *test = 'A';
    printf("%p: %c\n", test, *test);
    return 0;
}
