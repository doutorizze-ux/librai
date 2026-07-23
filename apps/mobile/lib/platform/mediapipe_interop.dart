export 'mediapipe_interop_stub.dart'
    if (dart.library.html) 'mediapipe_interop_web.dart'
    if (dart.library.js_util) 'mediapipe_interop_web.dart';
