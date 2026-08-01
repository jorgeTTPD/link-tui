# Maintainer: Jorge <jorgeescalera500@gmail.com>
pkgname=link-tui
pkgver=0.1.0
pkgrel=1
pkgdesc="TUI manager for Wi-Fi and Bluetooth networks"
arch=('any')
url="https://github.com/jorgeTTPD/link-tui"
license=('MIT')
depends=('python' 'python-textual>=0.80' 'python-rich' 'networkmanager' 'bluez' 'bluez-utils')
makedepends=('python-build' 'python-installer' 'python-wheel')
# setuptools names the sdist with an underscore: link_tui-${pkgver}.tar.gz
source=("link_tui-${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
  cd "${srcdir}/link_tui-${pkgver}"
  python -m build --wheel --no-isolation
}

package() {
  cd "${srcdir}/link_tui-${pkgver}"
  python -m installer --destdir="${pkgdir}" dist/*.whl
}
