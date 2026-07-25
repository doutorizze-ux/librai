import 'dart:js_interop';

@JS('libraiPlayVlibras')
external void _playVlibras(JSString gloss);

@JS('libraiSetVlibrasStage')
external void _setVlibrasStage(JSBoolean visible);

const bool hasOfficialVlibrasAvatar = true;

void playOfficialVlibrasSign(String label) {
  _playVlibras(label.toJS);
}

void setOfficialVlibrasStageVisible(bool visible) {
  _setVlibrasStage(visible.toJS);
}
