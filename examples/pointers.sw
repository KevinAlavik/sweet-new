extern printf(...) -> int;

fn main() -> int {
    var a: usize = 69;
    var ptr: usize* = &a;
    var pptr: usize** = &ptr;

    printf("Initial:\n");
    printf("a = %d, ptr = %p, *ptr = %d\n", a, ptr, *ptr);
    printf("pptr = %p, *pptr = %p, **pptr = %d\n", pptr, *pptr, **pptr);

    *ptr = 420;
    printf("\nAfter *ptr = 420:\n");
    printf("a = %d, *ptr = %d, **pptr = %d\n", a, *ptr, **pptr);

    **pptr = 1337;
    printf("\nAfter **pptr = 1337:\n");
    printf("a = %d, *ptr = %d, **pptr = %d\n", a, *ptr, **pptr);

    return 0;
}
