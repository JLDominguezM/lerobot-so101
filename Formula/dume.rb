# Fórmula Homebrew (receta documentada) para distribuir DUM-E como un comando del sistema.
#
# Estado: plantilla. Para usarla de verdad:
#   1) Publicá el paquete en PyPI (ver docs/dume.md) y poné aquí la URL del sdist + su sha256, o
#      apuntá `url` al repo git con `:using => :git, :tag => "vX.Y.Z"`.
#   2) LeRobot arrastra un stack ML pesado (torch, depthai, etc.). Para una fórmula
#      autocontenida, generá los bloques `resource` con:
#          brew update-python-resources Formula/dume.rb
#      Hasta entonces, lo más práctico es un tap que instale en un virtualenv vía pip.
#   3) Recordá que el arm/cámaras siguen siendo necesarios en runtime; la fórmula
#      sólo entrega los comandos `dume` y `cal`.
#
# Instalación local (tap propio):  brew install --build-from-source ./Formula/dume.rb
class Dume < Formula
  include Language::Python::Virtualenv

  desc "DUM-E TUI + cal CLI para operar el brazo SO-101 sobre LeRobot"
  homepage "https://github.com/armandomm09/so101"
  url "https://files.pythonhosted.org/packages/source/s/so101-dume/so101_dume-0.1.0.tar.gz"
  sha256 "REEMPLAZAR_TRAS_PUBLICAR_EN_PYPI"
  license "MIT"

  depends_on "python@3.12"

  def install
    # virtualenv_install_with_resources requiere los `resource` generados (ver nota arriba).
    virtualenv_install_with_resources
  end

  test do
    assert_match "DUM-E", shell_output("#{bin}/dume --help")
  end
end
