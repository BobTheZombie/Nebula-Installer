# Nebula Installer — graphical LPM Linux installer (preview)

Nebula now offers an original **Qt 6 / PySide6 graphical installation wizard**
for LPM Linux. It is designed for the LPM live environment and integrates with
the project's existing terminal installer. This is an early *mounted-target*
installer, **not** a fully automated disk partitioner.

## Graphical workflow

1. **Welcome:** see supported installation modes and storage limitations.
2. **Storage:** select an already mounted target root and its fstab root device,
   and enter other already mounted /boot, /home, or EFI partitions.
3. **Packages:** choose **Repository binaries** or **Build from source**; list
   optional repository bootstrap packages and the final desktop/system packages.
4. **Identity:** enter hostname, locale, timezone, user, and a password. OpenSSL
   converts passwords to SHA-512 crypt hashes; plaintext is not saved in plans.
5. **Review:** inspect exact target, package names, mount table, and type the
   destination to authorize installation.
6. **Install:** polkit runs a minimal, separately privileged Python worker.
   QProcess displays live output; the GUI stays unprivileged throughout.

**Commands**

- Repository: `lpm install --root TARGET pkg1 pkg2 …`
- Source: `chroot TARGET /usr/bin/env -i HOME=/root PATH=... /usr/bin/lpm buildpkg PACKAGE --yes`
- Optional bootstrap packages always use the repository. Source-mode target
  must have LPM, a compiler/toolchain, network access, and runtime mountpoints.

## Install the GUI

In a functioning LPM Linux live desktop with Python, PySide6, Textual, LPM,
OpenSSL, polkit (pkexec) and a desktop authentication agent:

```sh
git clone https://github.com/BobTheZombie/Nebula-Installer.git
cd Nebula-Installer
python3 -m pip install --user '.[gui]'
nebula-installer --gui
```

On LPM you can install `pyside6` and `polkit` from available package recipes
instead of using pip for these dependencies. Run the GUI as the **ordinary desktop
user**, *not sudo*, so that KDE's Wayland display remains accessible. The
separate worker is authorized via polkit.

## Prepare the target manually

**Carefully choose the correct destination** and create/mount partitions
*outside Nebula*. The following assumes the root partition has already been
prepared and mounted at `/mnt/lpm`:

```sh
sudo mkdir -p /mnt/lpm/{dev,proc,sys}
sudo mount --rbind /dev /mnt/lpm/dev
sudo mount --make-rslave /mnt/lpm/dev
sudo mount -t proc proc /mnt/lpm/proc
sudo mount --rbind /sys /mnt/lpm/sys
sudo mount --make-rslave /mnt/lpm/sys
```

Mount any chosen /home, /boot, or EFI partitions **under the target** before
starting the installer. The GUI requires those paths to be mountpoints.
The destination must itself be an existing mountpoint, and `/` is forbidden.

For source installations, the target must be a runnable LPM chroot with
`/usr/bin/env`, `lpm`, a complete build toolchain, and working DNS/network.
For example, set up `/etc/resolv.conf` inside the target appropriately.
Source builds run *inside that chroot*, never on the live host.

The installer generates sysconfig, writes /etc/fstab, and manages a user
account after installing the requested packages. **It does not** format or
partition disks, select a disk automatically, enroll secure boot, configure a
bootloader, or reboot. A complete, bootable system additionally requires you to
configure the kernel/initramfs, boot entries (e.g. systemd-boot or GRUB),
filesystem layout, and platform services. Test in a VM before touching
physical disks.

### Logs and safety

The GUI validates package identifiers, mountpoints, hostname, user input and
fstab entries, then rechecks them in the root worker. It blocks bootloader-hook
registration and automatic mount synchronization that belong to the older
terminal workflow. It refuses to begin without an explicit typed target
confirmation. Any package transaction can still overwrite files *inside the
selected target*, so have backups.

Run tests with `python3 -m pytest -q`. Headless tests cover command dispatch
and plan validation; PySide6 screens and complete installation require a real
Qt/Wayland environment, a live LPM target and deliberate manual testing.

---

## Legacy terminal installer

The older JSON and Textual wizard interface remains supported:

A Python-based installer for LuminOS backed by **LPM – the Linux Package
Manager**. The tool orchestrates filesystem preparation, package installation,
and post-install configuration using the helper scripts recently introduced to
the project, including:

- `lpm --sysconfig` for generating base system configuration
- the `fstab` helper for maintaining mount definitions
- the `update-grub` hook used during bootloader installation

## Usage

1. Create an installation description (see the configuration section below) and
   ensure the helper utilities provided by the live image – `lpm`,
   `nebula-fstab-helper`, and the `update-grub` hook – are available in `$PATH`.
2. Mount the target partitions under the directory referenced by
   `target_root` in your configuration.
3. Execute the installer:

   ```bash
   sudo python -m nebula_installer --config path/to/install.json
   ```

4. Review the log output. The installer is idempotent, so re-running it after
   adjusting the configuration reconciles the chroot with your desired state.

An interactive Textual-powered wizard is also available, offering a vibrant TUI
that gathers the target root directory, user credentials, storage layout, and
package selections. The wizard can optionally write the resulting configuration
to disk for later reuse:

```bash
sudo python -m nebula_installer --interactive --write-config install.json
```

The installer automatically loads the `lpmspec` JSON description exported by
LPM (defaulting to `/var/lib/lpm/maintainer/lpmspec.json`) to stay in sync with
the CLI surface. Set the `NEBULA_LPMSPEC_PATH` environment variable to point to
an alternate specification if necessary.

### Configuration reference

The configuration file is JSON and supports the following fields:

- `target_root`: Path to the mounted target root filesystem
- `hostname`: Hostname for the new system
- `timezone`: Timezone string (e.g. `UTC`)
- `locale`: Primary locale (e.g. `en_US.UTF-8`)
- `bootstrap_packages`: Packages used to bootstrap a minimal system via `lpm`
  before applying the remaining configuration. Defaults to
  `luminos-base`, `linux`, and `kernel-modules` if omitted.
- `packages`: Additional packages to install through `lpm`
- `partitions`: Array of partition objects with `device`, `mountpoint`,
  `filesystem`, `options`, `dump`, and `passno`
- `user`: Object describing the primary user with `username`, `password`,
  `groups`, and `shell`. The password value should already be hashed using a
  tool such as `openssl passwd -6`.

Example:

```json
{
  "target_root": "/mnt/luminos",
  "hostname": "luminos-host",
  "timezone": "UTC",
  "locale": "en_US.UTF-8",
  "bootstrap_packages": ["luminos-base", "linux", "kernel-modules"],
  "packages": ["luminos-desktop"],
  "partitions": [
    {"device": "/dev/sda1", "mountpoint": "/", "filesystem": "ext4"},
    {"device": "/dev/sda2", "mountpoint": "/home", "filesystem": "ext4"}
  ],
  "user": {
    "username": "lumina",
    "password": "$6$rounds=4096$example$YN4cR9XZuXgQvb8nZx0SntzT0dXoVwq5m7YhV8csfZ5lC6zUQ8xqJ6E2N1k7L6",
    "groups": ["wheel"],
    "shell": "/bin/bash"
  }
}
```

### Building a fresh chroot

To create a brand-new LuminOS chroot and then apply the installer:

```bash
sudo mkdir -p /mnt/luminos
# Partition the disk as desired, then mount each filesystem under /mnt/luminos
sudo mount /dev/disk/by-partuuid/<root-partuuid> /mnt/luminos
sudo mount /dev/disk/by-partuuid/<home-partuuid> /mnt/luminos/home

# Bootstrap a minimal system into the target root with lpm
sudo lpm install --root=/mnt/luminos luminos-base linux kernel-modules

# Populate /etc/fstab, sysconfig, user accounts, and hooks using the installer
sudo python -m nebula_installer --config install.json

# Optionally enter the environment for additional manual configuration
sudo chroot /mnt/luminos /usr/bin/env -i HOME=/root TERM="$TERM" /bin/bash
```

Adjust the package list passed to `lpm install` to match the profiles you want
available in the new system. The installer will overlay the configuration on top
of the freshly bootstrapped root, ensure the user account exists with the
expected password, update `fstab`, and register the bootloader hook.
