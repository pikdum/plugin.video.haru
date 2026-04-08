{
  pkgs,
  lib,
  config,
  ...
}:
{
  languages.python.enable = true;
  languages.nix.enable = true;

  packages = [ pkgs.ruff ];

  git-hooks.hooks = {
    ruff.enable = true;
    ruff-format.enable = true;
    nixfmt.enable = true;
  };
}
