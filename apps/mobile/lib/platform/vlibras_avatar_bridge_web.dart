import 'dart:js_interop';

@JS('libraiPlayVlibras')
external void _playVlibras(JSString gloss);

const bool hasOfficialVlibrasAvatar = true;

void playOfficialVlibrasSign(String label) {
  _playVlibras(label.toJS);
}
