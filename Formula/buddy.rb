class Buddy < Formula
  include Language::Python::Virtualenv

  desc "RPG buddy for Claude Code — ASCII companion that gains XP from your prompts"
  homepage "https://github.com/pgarfagnoli/homebrew-buddy"
  url "https://github.com/pgarfagnoli/homebrew-buddy/archive/refs/tags/v0.2.0.tar.gz"
  sha256 "55c54f988a1812198255d74e43733f61f03ac4ab047f8ae921a1f11330618590"
  license "MIT"

  depends_on "python@3.12"
  depends_on "tmux"

  # TODO: run `brew update-python-resources buddy` (or
  # `poet -f buddy`) after a venv with `mcp` is available, to generate
  # the full resource block for `mcp` and its transitive dependencies.
  resource "mcp" do
    url "TODO_FILL_WITH_PYPI_SDIST_URL"
    sha256 "TODO_FILL_WITH_PYPI_SDIST_SHA256"
  end

  def install
    # Python package lives in a subfolder of the tap repo.
    cd "buddy" do
      virtualenv_install_with_resources
    end
  end

  test do
    assert_predicate bin/"buddy", :exist?
    assert_predicate bin/"buddy-install", :exist?
  end
end
