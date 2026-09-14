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

  enterTest = "python -m unittest discover -s tests";

  git-hooks.hooks = {
    ruff.enable = true;
    ruff-format.enable = true;
    nixfmt.enable = true;
  };
}
