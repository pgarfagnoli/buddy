class McpCreatureBot < Formula
  include Language::Python::Virtualenv

  desc "RPG buddy for Claude Code — ASCII companion that gains XP from your prompts"
  homepage "https://github.com/pgarfagnoli/homebrew-buddy"
  url "https://github.com/pgarfagnoli/homebrew-buddy/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "09811181473ad198b8af71214759f0e1d87ca62eb933cc1ecebee6961eeaf47a"
  license "MIT"

  depends_on "python@3.12"
  depends_on "tmux"

  # TODO: run `brew update-python-resources mcp-creature-bot` (or
  # `poet -f mcp-creature-bot`) after the tag is cut to generate the
  # full resource block for `mcp` and its transitive dependencies.
  resource "mcp" do
    url "TODO_FILL_WITH_PYPI_SDIST_URL"
    sha256 "TODO_FILL_WITH_PYPI_SDIST_SHA256"
  end

  def install
    # Python package lives in a subfolder of the tap repo.
    cd "mcp-creature-bot" do
      virtualenv_install_with_resources
    end
  end

  test do
    assert_match "mcp-creature-bot", shell_output("#{bin}/mcp-creature-bot --help 2>&1", 1)
  end
end
