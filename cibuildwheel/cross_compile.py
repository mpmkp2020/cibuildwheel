import os
import subprocess
from typing import Dict, Optional
from .docker_container import DockerContainer

# Docker container which will be used to resove dependencies
# while crosss compiling the wheels
native_docker_images = {
    "aarch64": "quay.io/pypa/manylinux2014_aarch64"
}

def platform_tag_to_arch(platform_tag):
    return platform_tag.split('_')[1][:-2]

# Setup environment to prepare the toolchain
class TargetArchEnvUtil:
    def __init__(self,
            env,
            target_arch=None
    ):
        self.tmp = '/tmp'
        self.host = '/host'
        self.deps = '/install_deps'
        self.host_machine_tmp_in_container = self.host + self.tmp
        self.host_machine_deps_in_container = self.host_machine_tmp_in_container + self.deps
        self.host_machine_deps_usr_in_container = self.host_machine_tmp_in_container + self.deps + "/usr"
        self.host_machine_deps_usr_out_container = self.tmp + self.deps + "/usr"
        self.toolchain_deps = env['CROSS_ROOT'] + '/aarch64-unknown-linux-gnueabi/'

def setup_qemu():
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--privileged",
            "hypriot/qemu-register"
        ],
        check=True,
    )

# Install the dependencies into the toolchain
def xc_before_all(
        docker: DockerContainer,
        before_all_prepared: str,
        target_arch: str,
        env: Optional[Dict[str, str]] = None
):
    target_arch_env=TargetArchEnvUtil(env, target_arch)

    cmds=[cmd.strip().replace('\t', ' ') for cmd in before_all_prepared.split("&&")]

    # Copy install_deps.sh script from container's tmp to host machine tmp and use it
    docker.call(
        [
            'cp',
            target_arch_env.tmp+'/install_deps.sh',
            target_arch_env.host_machine_tmp_in_container
        ]
    )

    for cmd in cmds:
        if cmd.startswith('yum '):

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
                    target_arch_env.host_machine_tmp_in_container+'/install_deps.sh "' + cmd + '"'
                ],
                check=True,
            )

            # The instaleld dependencies are in /tmp/install_deps on host machine.
            # Copy them into the toolchain
            dir_list = os.listdir(target_arch_env.host_machine_deps_usr_out_container)
            for dir in dir_list:
                docker.call(
                    [
                        'cp',
                        '-rf',
                        target_arch_env.host_machine_deps_usr_in_container + "/" + dir,
                        target_arch_env.toolchain_deps
                    ]
                )
        else:
            docker.call(["sh", "-c", cmd], env=env)
