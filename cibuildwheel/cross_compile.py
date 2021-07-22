import os
import subprocess

# Docker container which will be used to resove dependencies
# while crosss compiling the wheels
native_docker_images = {
    "aarch64": "quay.io/pypa/manylinux2014_aarch64"
}

# Plat-name passed to build the wheels
plat_name = {
    "aarch64": "manylinux2014-aarch64"
}

def platform_tag_to_arch(platform_tag):
    return platform_tag.split('_')[1][:-2]

# Setup environment to prepare the toolchain
class TargetArchEnvUtil:
    def __init__(self, docker_env, target_arch=None):
        self.tmp = '/tmp'
        self.host = '/host'
        self.deps = '/install_deps'
        self.host_machine_tmp_in_container = self.host + self.tmp
        self.host_machine_deps_usr_in_container = self.host_machine_tmp_in_container + self.deps + "/usr"
        self.host_machine_deps_usr_out_container = self.tmp + self.deps + "/usr"
        self.toolchain_deps = docker_env['CROSS_ROOT'] + '/aarch64-unknown-linux-gnueabi/'

# Install the dependencies into the toolchain
def prepare_toolchain(docker, before_all_prepared, target_arch):
    docker_env = docker.get_environment()
    target_arch_env=TargetArchEnvUtil(docker_env, target_arch)
    print("\nRegistering qemu to run ppc64le/AArch64 docker containers...\n")
    docker.call(['docker', 'run', '--rm', '--privileged',
        'hypriot/qemu-register'])

    # Mapped volume in docker call is respect to host machine, so copy 
    # install_deps.sh script from container's tmp to host machine tmp and use it
    docker.call(['cp', target_arch_env.tmp+'/install_deps.sh', target_arch_env.host_machine_tmp_in_container])

    # Install the dependencies into the emulated docker container and
    # Copy back the installed files into host machine
    print("\nInstalling package in target's native container and copy the artifacts into toolchain\n");
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--volume=/:/host",  # ignored on CircleCI
            native_docker_images[target_arch],
            "bash",
            "-c",
            target_arch_env.host_machine_tmp_in_container+'/install_deps.sh "' + before_all_prepared + '"'
            ],
        check=True,
    )


    # The instaleld dependencies are in /tmp/install_deps on host machine.
    # Copy them into the toolchain
    dir_list = os.listdir(target_arch_env.host_machine_deps_usr_out_container)
    for dir in dir_list:
        docker.call(['cp', '-r',  target_arch_env.host_machine_deps_usr_in_container + "/" + dir, target_arch_env.toolchain_deps])
    
