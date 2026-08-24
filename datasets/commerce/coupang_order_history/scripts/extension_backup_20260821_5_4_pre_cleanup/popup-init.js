'use strict';

// MV3 확장 페이지는 인라인 스크립트를 실행하지 못한다. 그래서 파일로 분리한다.
// background.js 는 이 표시를 보고 리스너 등록을 건너뛴다. 팝업에서는 컨트롤러만 쓴다.
globalThis.__coupangPopup = true;
