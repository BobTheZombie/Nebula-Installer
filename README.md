# Nebula Installer

A Python-based installer for NebulaOS backed by `lpm`. The tool orchestrates
filesystem preparation, package installation, and post-install configuration
using the helper scripts recently introduced to the project, including:

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

An interactive wizard is also available, which prompts for the target root
directory, user credentials, and package selections. The wizard can optionally
write the resulting configuration to disk for later reuse:

```bash
sudo python -m nebula_installer --interactive --write-config install.json
```

### Configuration reference

The configuration file is JSON and supports the following fields:

- `target_root`: Path to the mounted target root filesystem
- `hostname`: Hostname for the new system
- `timezone`: Timezone string (e.g. `UTC`)
- `locale`: Primary locale (e.g. `en_US.UTF-8`)
- `bootstrap_packages`: Packages used to bootstrap a minimal system via `lpm`
  before applying the remaining configuration. Defaults to
  `nebula-base`, `linux`, and `kernel-modules` if omitted.
- `packages`: Additional packages to install through `lpm`
- `partitions`: Array of partition objects with `device`, `mountpoint`,
  `filesystem`, `options`, `dump`, and `passno`
- `user`: Object describing the primary user with `username`, `password`,
  `groups`, and `shell`. The password value should already be hashed using a
  tool such as `openssl passwd -6`.

Example:

```json
{
  "target_root": "/mnt/nebula",
  "hostname": "nebula-host",
  "timezone": "UTC",
  "locale": "en_US.UTF-8",
  "bootstrap_packages": ["nebula-base", "linux", "kernel-modules"],
  "packages": ["nebula-desktop"],
  "partitions": [
    {"device": "/dev/sda1", "mountpoint": "/", "filesystem": "ext4"},
    {"device": "/dev/sda2", "mountpoint": "/home", "filesystem": "ext4"}
  ],
  "user": {
    "username": "nebula",
    "password": "$6$rounds=4096$example$YN4cR9XZuXgQvb8nZx0SntzT0dXoVwq5m7YhV8csfZ5lC6zUQ8xqJ6E2N1k7L6", 
    "groups": ["wheel"],
    "shell": "/bin/bash"
  }
}
```

### Building a fresh chroot

To create a brand-new Nebula chroot and then apply the installer:

```bash
sudo mkdir -p /mnt/nebula
# Partition the disk as desired, then mount each filesystem under /mnt/nebula
sudo mount /dev/disk/by-partuuid/<root-partuuid> /mnt/nebula
sudo mount /dev/disk/by-partuuid/<home-partuuid> /mnt/nebula/home

# Bootstrap a minimal system into the target root with lpm
sudo lpm install --root=/mnt/nebula nebula-base linux kernel-modules

# Populate /etc/fstab, sysconfig, user accounts, and hooks using the installer
sudo python -m nebula_installer --config install.json

# Optionally enter the environment for additional manual configuration
sudo chroot /mnt/nebula /usr/bin/env -i HOME=/root TERM="$TERM" /bin/bash
```

Adjust the package list passed to `lpm install` to match the profiles you want
available in the new system. The installer will overlay the configuration on top
of the freshly bootstrapped root, ensure the user account exists with the
expected password, update `fstab`, and register the bootloader hook.
