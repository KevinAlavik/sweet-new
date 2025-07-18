global _start
extern main
section .text
_start:
    call main
    mov edi, eax            ; exit code for syscall
    mov eax, 60             ; sys_exit
    syscall
