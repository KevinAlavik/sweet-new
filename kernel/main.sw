fn println(s: u8*) -> void {
    asm {
        mov rsi, s;
        loop_start:
        mov al, [rsi];
        cmp al, 0;
        je loop_end;
        out 233, al;
        inc rsi;
        jmp loop_start;
        loop_end:
    }
}

fn kmain() -> void {
    println("Hello from a test kernel written in Sweet (v2)\n");
    asm { hlt }
}