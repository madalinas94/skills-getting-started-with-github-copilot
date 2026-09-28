// Împachetează PNG-urile din assets/icons/ într-un singur assets/icon.ico
// (format ICO cu intrări PNG, suportat de Windows Vista+ și electron-builder).
const fs = require('fs');
const path = require('path');

const dir = path.join(__dirname, '..', 'assets', 'icons');
const sizes = [16, 24, 32, 48, 64, 128, 256];
const images = sizes.map(s => ({ size: s, data: fs.readFileSync(path.join(dir, `icon-${s}.png`)) }));

const header = Buffer.alloc(6);
header.writeUInt16LE(0, 0);
header.writeUInt16LE(1, 2);
header.writeUInt16LE(images.length, 4);

let offset = 6 + 16 * images.length;
const entries = images.map(({ size, data }) => {
  const e = Buffer.alloc(16);
  e.writeUInt8(size >= 256 ? 0 : size, 0);
  e.writeUInt8(size >= 256 ? 0 : size, 1);
  e.writeUInt8(0, 2);
  e.writeUInt8(0, 3);
  e.writeUInt16LE(1, 4);
  e.writeUInt16LE(32, 6);
  e.writeUInt32LE(data.length, 8);
  e.writeUInt32LE(offset, 12);
  offset += data.length;
  return e;
});

const out = path.join(__dirname, '..', 'assets', 'icon.ico');
fs.writeFileSync(out, Buffer.concat([header, ...entries, ...images.map(i => i.data)]));
console.log('Scris', out);
