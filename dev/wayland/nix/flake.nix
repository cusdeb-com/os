{
  description = "CusDeb Wayland prototype and QEMU development tools";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    flake-parts.inputs.nixpkgs-lib.follows = "nixpkgs";
  };

  outputs = inputs:
    inputs.flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" ];
      perSystem = { pkgs, ... }: {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            qemu
            cloud-utils
            cdrkit
            curl
            jq
            openssh
            shellcheck
            (python3.withPackages (ps: [ ps.pillow ]))
          ];
        };
      };
    };
}
