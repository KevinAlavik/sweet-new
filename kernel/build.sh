#!/bin/bash
set -e

KERNEL_SRC="kernel/main.sw"
KERNEL_OUT="out"
ISO_ROOT="iso_root"
ISO_OUT="uuk.iso"
LIMINE_DIR="limine"
LIMINE_CONF="kernel/limine.conf"
OVMF_DIR="ovmf"
OVMF_FD="${OVMF_DIR}/ovmf-code-x86_64.fd"

if [ "$(uname -s)" = "Linux" ]; then
    IS_WINDOWS=0
    LIMINE_EXE="${LIMINE_DIR}/limine"
    XORRISO_CMD="xorriso"
else
    IS_WINDOWS=1
    LIMINE_EXE="${LIMINE_DIR}/limine.exe"
    XORRISO_CMD="xorriso.exe"
fi

echo "[*] Compiling kernel..."
./sweet.py ${KERNEL_SRC} --freestanding --ldflags "-nostdlib -static -z max-page-size=0x1000 -Wl,--gc-sections -T kernel/linker.ld -Wl,-m,elf_x86_64"

echo "[*] Setting up directories..."
mkdir -p ${ISO_ROOT}/boot/limine
mkdir -p ${ISO_ROOT}/EFI/BOOT
mkdir -p ${OVMF_DIR}

if [ ! -d "${LIMINE_DIR}" ]; then
    echo "[*] Cloning Limine..."
    git clone https://github.com/limine-bootloader/limine.git --branch=v8.x-binary --depth=1 ${LIMINE_DIR}
fi
if [ ${IS_WINDOWS} -eq 0 ]; then
    echo "[*] Building Limine..."
    make -C ${LIMINE_DIR} CC=gcc CFLAGS="-g -O2 -pipe"
fi

if [ ! -f "${OVMF_FD}" ]; then
    echo "[*] Downloading OVMF firmware..."
    curl -L -o ${OVMF_FD} https://github.com/osdev0/edk2-ovmf-nightly/releases/latest/download/ovmf-code-x86_64.fd
fi

echo "[*] Copying files to ISO structure..."
cp ${KERNEL_OUT} ${ISO_ROOT}/boot/kernel
cp ${LIMINE_CONF} ${ISO_ROOT}/boot/limine/ || { echo "[!] Error: limine.conf not found"; exit 1; }
cp ${LIMINE_DIR}/limine-bios.sys ${ISO_ROOT}/boot/limine/
cp ${LIMINE_DIR}/limine-bios-cd.bin ${ISO_ROOT}/boot/limine/
cp ${LIMINE_DIR}/limine-uefi-cd.bin ${ISO_ROOT}/boot/limine/
cp ${LIMINE_DIR}/BOOTX64.EFI ${ISO_ROOT}/EFI/BOOT/
cp ${LIMINE_DIR}/BOOTIA32.EFI ${ISO_ROOT}/EFI/BOOT/

echo "[*] Generating bootable ISO..."
${XORRISO_CMD} -as mkisofs \
    -R -r -J \
    -b boot/limine/limine-bios-cd.bin \
    -no-emul-boot -boot-load-size 4 -boot-info-table -hfsplus \
    -apm-block-size 2048 \
    --efi-boot boot/limine/limine-uefi-cd.bin \
    -efi-boot-part --efi-boot-image --protective-msdos-label \
    ${ISO_ROOT} -o ${ISO_OUT}

echo "[*] Installing Limine to ISO..."
${LIMINE_EXE} bios-install ${ISO_OUT}

echo "[+] Bootable ISO created: ${ISO_OUT}"

if [ "$1" = "run" ]; then
    echo "[*] Running QEMU..."
    qemu-system-x86_64 \
        -M q35 \
        -drive if=pflash,unit=0,format=raw,file=${OVMF_FD},readonly=on \
        -cdrom ${ISO_OUT} \
        -smp 4 \
        -serial file:com1.log \
        -debugcon stdio
fi