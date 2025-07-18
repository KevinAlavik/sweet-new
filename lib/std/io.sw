extern printf(...) -> int;

fn println(str: string) -> void {
    printf("%s\n", str);
}