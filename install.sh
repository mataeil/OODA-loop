#!/bin/bash
# OODA-loop — Global Install Script
# Creates symlinks in ~/.claude/skills/ so OODA-loop skills are available in all projects.
#
# Usage:
#   git clone https://github.com/mataeil/OODA-loop.git ~/.ooda-loop
#   ~/.ooda-loop/install.sh
#
# To uninstall:
#   ~/.ooda-loop/install.sh --uninstall

set -e

OODA_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"

if [ "$1" = "--uninstall" ]; then
  echo "Removing OODA-loop skills from $SKILLS_DIR..."
  for skill in "$OODA_DIR"/skills/*/; do
    name=$(basename "$skill")
    [ -L "$SKILLS_DIR/$name" ] && rm "$SKILLS_DIR/$name" && echo "  Removed $name"
  done
  echo "Done. Skills uninstalled."
  exit 0
fi

echo "Installing OODA-loop skills to $SKILLS_DIR..."
mkdir -p "$SKILLS_DIR"

for skill in "$OODA_DIR"/skills/*/; do
  name=$(basename "$skill")
  if [ -e "$SKILLS_DIR/$name" ] && [ ! -L "$SKILLS_DIR/$name" ]; then
    echo "  [SKIP] $name — file already exists (not a symlink). Remove manually if needed."
  else
    ln -sfn "$skill" "$SKILLS_DIR/$name"
    echo "  Linked $name"
  fi
done

echo ""
echo "OODA-loop installed. Skills available in all projects."
echo ""
echo "Next steps:"
echo "  cd your-project/"
echo "  /ooda-setup          # configure OODA-loop for this project"
echo ""
echo "To update:  cd ~/.ooda-loop && git pull"
echo "To remove:  ~/.ooda-loop/install.sh --uninstall"
