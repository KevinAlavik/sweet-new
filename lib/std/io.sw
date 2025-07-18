fn write(fd: int, buf: u8*, len: int) -> int {
    asm {
        mov rax, 1;
        syscall;
    }
}

extern printf(...) -> int;
fn println(str: string) -> void {
    printf("%s\n", str);
}