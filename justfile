set shell := ["bash", "-euo", "pipefail", "-c"]

package:
    cd .. && rm -f plugin.video.haru.zip && nix run nixpkgs#zip -- -r plugin.video.haru.zip plugin.video.haru -x 'plugin.video.haru/.*' -x '*/__pycache__/*'
