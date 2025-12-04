#!/usr/bin/env python3
"""
Advanced HWP MCP Server
고도화된 한글 MCP 서버 - 한글의 모든 기능을 제어할 수 있는 MCP 서버
"""

import logging
import sys
import os
import re
from typing import Optional, Dict, Any, List, Tuple
import json

try:
    from mcp.server.fastmcp import FastMCP
    import win32com.client
    import pythoncom
    import win32api
    import win32con
    import win32gui
    import win32process
    import ctypes
except ImportError as e:
    print(f"필수 패키지가 설치되지 않음: {e}", file=sys.stderr)
    print("다음 명령어로 패키지를 설치하세요:", file=sys.stderr)
    print("pip install mcp fastmcp pywin32", file=sys.stderr)
    sys.exit(1)

# 로깅 설정 - MCP는 stdout을 JSON-RPC로 사용하므로 stderr로만 출력
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hwp_mcp.log'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# MCP 서버 초기화
mcp = FastMCP("Advanced HWP Server")

class AdvancedHwpController:
    """고급 한글 컨트롤러 클래스"""
    
    def __init__(self):
        """한글 COM 객체 초기화"""
        self.hwp = None
        self.is_initialized = False
        self.current_document = None
        
    def initialize(self):
        """한글 COM 객체 초기화"""
        try:
            pythoncom.CoInitialize()

            # 한글 프로그램이 설치되어 있는지 확인
            try:
                self.hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
            except:
                # gencache가 실패하면 일반 Dispatch 사용
                self.hwp = win32com.client.Dispatch("HWPFrame.HwpObject")

            # ===== 자동화 모드 설정: 모든 확인 대화상자 자동 승인 =====

            # 1. 파일 경로 체크 대화상자 비활성화
            try:
                self.hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
            except:
                pass

            # 2. 보안 경고 대화상자 비활성화
            try:
                self.hwp.RegisterModule("SecurityModule", "")
            except:
                pass

            # 3. 개인정보 보호 기능 비활성화 (대화상자 방지)
            try:
                self.hwp.SetPrivateInfoProtection(0)
            except:
                pass

            # 4. 메시지 박스 자동 응답 설정 (모든 확인창 자동 Yes)
            try:
                # MessageBoxMode: 0=자동응답, 1=대화상자표시
                self.hwp.MessageBoxMode = 0
            except:
                pass

            # 5. 편집 모드를 자동화 모드로 설정
            try:
                self.hwp.EditMode = 1  # 1=자동화모드, 0=일반모드
            except:
                pass

            # 6. 화면 업데이트 일시 중지 (성능 향상)
            try:
                self.hwp.SetMessageBoxMode(0)  # 0=자동, 1=표시
            except:
                pass

            # 한글 창을 보이게 설정
            if self.hwp.XHwpWindows.Count > 0:
                self.hwp.XHwpWindows.Item(0).Visible = True

            self.is_initialized = True
            logger.info("한글 COM 객체 초기화 완료 (자동화 모드 활성화)")
            return True

        except Exception as e:
            logger.error(f"한글 COM 객체 초기화 실패: {e}")
            return False
    
    def __del__(self):
        """리소스 정리"""
        try:
            if self.is_initialized:
                pythoncom.CoUninitialize()
        except:
            pass
    
    def check_initialization(self):
        """초기화 상태 확인"""
        if not self.is_initialized:
            if not self.initialize():
                raise Exception("한글 프로그램이 설치되지 않았거나 초기화할 수 없습니다.")
        return True

# 전역 컨트롤러 인스턴스
hwp_controller = AdvancedHwpController()

@mcp.tool()
def initialize_hwp() -> str:
    """한글 프로그램을 초기화합니다."""
    try:
        if hwp_controller.initialize():
            return "한글 프로그램 초기화 성공"
        else:
            return "한글 프로그램 초기화 실패"
    except Exception as e:
        logger.error(f"초기화 중 오류: {e}")
        return f"초기화 실패: {e}"

@mcp.tool()
def get_running_hwp_documents() -> str:
    """실행 중인 한글에서 열린 문서 목록을 조회합니다."""
    try:
        pythoncom.CoInitialize()
        
        hwp = None
        
        # 1. 이미 연결된 컨트롤러가 있으면 사용
        if hwp_controller.is_initialized and hwp_controller.hwp:
            hwp = hwp_controller.hwp
        else:
            # 2. GetActiveObject 시도
            try:
                hwp = win32com.client.GetActiveObject("HWPFrame.HwpObject")
            except:
                pass
            
            # 3. GetActiveObject 실패 시 Dispatch로 연결 시도
            if hwp is None:
                try:
                    hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
                    if hwp.XHwpDocuments.Count == 0:
                        return "실행 중인 한글 프로그램이 없습니다. initialize_hwp()로 시작하세요."
                except:
                    return "실행 중인 한글 프로그램이 없습니다. initialize_hwp()로 시작하세요."
        
        # 열린 문서 목록 가져오기
        doc_count = hwp.XHwpDocuments.Count
        if doc_count == 0:
            return "한글이 실행 중이지만 열린 문서가 없습니다."
        
        documents = []
        for i in range(doc_count):
            doc = hwp.XHwpDocuments.Item(i)
            doc_path = doc.Path if doc.Path else "(새 문서)"
            doc_name = doc.Path.split("\\")[-1] if doc.Path else f"새 문서 {i+1}"
            documents.append({
                "index": i,
                "name": doc_name,
                "path": doc_path
            })
        
        result = f"현재 연결된 한글에서 열린 문서 ({doc_count}개):\n"
        for doc in documents:
            result += f"  [{doc['index']}] {doc['name']}\n"
            result += f"      경로: {doc['path']}\n"
        
        # 여러 한글 프로세스 확인 안내
        try:
            import subprocess
            result_proc = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Hwp.exe', '/FO', 'CSV', '/NH'], 
                                        capture_output=True, text=True)
            hwp_count = len([line for line in result_proc.stdout.strip().split('\n') if 'Hwp.exe' in line])
            if hwp_count > 1:
                result += f"\n⚠️ 주의: 한글 프로그램이 {hwp_count}개 실행 중입니다.\n"
                result += "   다른 인스턴스에 연결하려면 list_all_hwp_windows()를 호출하세요."
        except:
            pass
        
        logger.info(f"열린 문서 목록 조회 완료: {doc_count}개")
        return result
        
    except Exception as e:
        logger.error(f"문서 목록 조회 실패: {e}")
        return f"문서 목록 조회 실패: {e}"

@mcp.tool()
def list_all_hwp_windows() -> str:
    """실행 중인 모든 한글 창 목록을 조회합니다. (창 제목으로 파일명 확인)"""
    try:
        hwp_windows = []
        
        def enum_windows_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                window_text = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                
                if 'Hwp' in class_name or '한글' in window_text or window_text.endswith('.hwp'):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    results.append({
                        'hwnd': hwnd,
                        'title': window_text,
                        'class': class_name,
                        'pid': pid
                    })
            return True
        
        win32gui.EnumWindows(enum_windows_callback, hwp_windows)
        
        if not hwp_windows:
            return "실행 중인 한글 창을 찾을 수 없습니다."
        
        result = f"실행 중인 한글 창 ({len(hwp_windows)}개):\n"
        for i, win in enumerate(hwp_windows):
            result += f"  [{i}] {win['title']}\n"
            result += f"      PID: {win['pid']}, HWND: {win['hwnd']}\n"
        
        result += "\n특정 창에 연결하려면 connect_to_hwp_window(파일명 일부)를 호출하세요."
        
        logger.info(f"한글 창 목록 조회: {len(hwp_windows)}개")
        return result
        
    except Exception as e:
        logger.error(f"한글 창 목록 조회 실패: {e}")
        return f"한글 창 목록 조회 실패: {e}"

@mcp.tool()
def connect_to_hwp_window(search_text: str) -> str:
    """특정 파일명이 포함된 한글 창을 활성화하고 연결합니다."""
    try:
        pythoncom.CoInitialize()
        
        hwp_windows = []
        
        def enum_windows_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                window_text = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                
                if 'Hwp' in class_name or '한글' in window_text or window_text.endswith('.hwp'):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    results.append({
                        'hwnd': hwnd,
                        'title': window_text,
                        'class': class_name,
                        'pid': pid
                    })
            return True
        
        win32gui.EnumWindows(enum_windows_callback, hwp_windows)
        
        if not hwp_windows:
            return "실행 중인 한글 창을 찾을 수 없습니다."
        
        # 검색어가 포함된 창 찾기
        target_window = None
        for win in hwp_windows:
            if search_text.lower() in win['title'].lower():
                target_window = win
                break
        
        if target_window is None:
            titles = [w['title'] for w in hwp_windows]
            return f"'{search_text}'이(가) 포함된 창을 찾을 수 없습니다.\n실행 중인 창: {titles}"
        
        # 해당 창 활성화
        hwnd = target_window['hwnd']
        
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        
        try:
            win32gui.SetForegroundWindow(hwnd)
        except:
            try:
                win32gui.BringWindowToTop(hwnd)
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            except:
                pass
        
        import time
        time.sleep(0.3)
        
        try:
            hwp_controller.hwp = win32com.client.GetActiveObject("HWPFrame.HwpObject")
        except:
            hwp_controller.hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
        
        hwp_controller.is_initialized = True
        
        doc_count = hwp_controller.hwp.XHwpDocuments.Count
        if doc_count > 0:
            current_doc = hwp_controller.hwp.XHwpDocuments.Item(0)
            hwp_controller.current_document = current_doc.Path if current_doc.Path else "새 문서"
        
        logger.info(f"한글 창 연결 완료: {target_window['title']}")
        return f"'{target_window['title']}' 창에 연결되었습니다. (열린 문서: {doc_count}개)"
        
    except Exception as e:
        logger.error(f"한글 창 연결 실패: {e}")
        return f"한글 창 연결 실패: {e}"

@mcp.tool()
def connect_to_running_hwp() -> str:
    """이미 실행 중인 한글 프로그램에 연결합니다."""
    try:
        pythoncom.CoInitialize()
        
        hwp = None
        
        try:
            hwp = win32com.client.GetActiveObject("HWPFrame.HwpObject")
        except:
            pass
        
        if hwp is None:
            try:
                hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
                if hwp.XHwpDocuments.Count == 0:
                    hwp_controller.hwp = hwp
                    hwp_controller.is_initialized = True
                    return "실행 중인 한글이 없어 새로 시작했습니다. (열린 문서: 0개)"
            except Exception as e:
                return f"한글 연결 실패: {e}"
        
        hwp_controller.hwp = hwp
        hwp_controller.is_initialized = True
        
        doc_count = hwp_controller.hwp.XHwpDocuments.Count
        if doc_count > 0:
            current_doc = hwp_controller.hwp.XHwpDocuments.Item(0)
            hwp_controller.current_document = current_doc.Path if current_doc.Path else "새 문서"
        
        logger.info("실행 중인 한글에 연결 완료")
        return f"실행 중인 한글에 연결되었습니다. (열린 문서: {doc_count}개)"
        
    except Exception as e:
        logger.error(f"한글 연결 실패: {e}")
        return f"한글 연결 실패: {e}"

@mcp.tool()
def switch_to_document(file_name: str) -> str:
    """열린 문서 중 특정 파일로 전환합니다. 파일명 일부만 입력해도 됩니다."""
    try:
        pythoncom.CoInitialize()
        
        hwp = None
        
        if hwp_controller.is_initialized and hwp_controller.hwp:
            hwp = hwp_controller.hwp
        else:
            try:
                hwp = win32com.client.GetActiveObject("HWPFrame.HwpObject")
            except:
                pass
            
            if hwp is None:
                try:
                    hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
                    if hwp.XHwpDocuments.Count == 0:
                        return "실행 중인 한글 프로그램이 없습니다."
                except:
                    return "실행 중인 한글 프로그램이 없습니다."
        
        doc_count = hwp.XHwpDocuments.Count
        if doc_count == 0:
            return "열린 문서가 없습니다."
        
        found_doc = None
        found_index = -1
        
        for i in range(doc_count):
            doc = hwp.XHwpDocuments.Item(i)
            doc_path = doc.Path if doc.Path else ""
            doc_name = doc_path.split("\\")[-1] if doc_path else f"새 문서 {i+1}"
            
            if file_name.lower() in doc_name.lower() or file_name.lower() in doc_path.lower():
                found_doc = doc
                found_index = i
                break
        
        if found_doc is None:
            return f"'{file_name}'이(가) 포함된 문서를 찾을 수 없습니다."
        
        hwp.XHwpDocuments.Item(found_index).SetActive()
        
        hwp_controller.hwp = hwp
        hwp_controller.is_initialized = True
        hwp_controller.current_document = found_doc.Path
        
        doc_name = found_doc.Path.split("\\")[-1] if found_doc.Path else f"새 문서"
        logger.info(f"문서 전환 완료: {doc_name}")
        return f"'{doc_name}' 문서로 전환했습니다."
        
    except Exception as e:
        logger.error(f"문서 전환 실패: {e}")
        return f"문서 전환 실패: {e}"

@mcp.tool()
def get_active_document_info() -> str:
    """현재 활성화된 문서의 정보를 조회합니다."""
    try:
        pythoncom.CoInitialize()
        
        hwp = None
        
        if hwp_controller.is_initialized and hwp_controller.hwp:
            hwp = hwp_controller.hwp
        else:
            try:
                hwp = win32com.client.GetActiveObject("HWPFrame.HwpObject")
            except:
                pass
            
            if hwp is None:
                try:
                    hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
                    if hwp.XHwpDocuments.Count == 0:
                        return "실행 중인 한글 프로그램이 없습니다."
                except:
                    return "실행 중인 한글 프로그램이 없습니다."
        
        doc_count = hwp.XHwpDocuments.Count
        if doc_count == 0:
            return "열린 문서가 없습니다."
        
        active_doc = hwp.XHwpDocuments.Item(0)
        doc_path = active_doc.Path if active_doc.Path else "(새 문서 - 저장되지 않음)"
        doc_name = doc_path.split("\\")[-1] if active_doc.Path else "새 문서"
        
        page_count = hwp.PageCount
        
        result = f"""현재 활성 문서 정보:
- 파일명: {doc_name}
- 경로: {doc_path}
- 페이지 수: {page_count}
- 총 열린 문서 수: {doc_count}개"""
        
        logger.info(f"활성 문서 정보 조회: {doc_name}")
        return result
        
    except Exception as e:
        logger.error(f"문서 정보 조회 실패: {e}")
        return f"문서 정보 조회 실패: {e}"

@mcp.tool()
def create_document() -> str:
    """새 한글 문서를 생성합니다."""
    try:
        hwp_controller.check_initialization()
        
        hwp_controller.hwp.HAction.Run("FileNew")
        hwp_controller.current_document = "new_document"
        
        logger.info("새 문서 생성 완료")
        return "새 문서가 생성되었습니다."
        
    except Exception as e:
        logger.error(f"문서 생성 실패: {e}")
        return f"문서 생성 실패: {e}"

@mcp.tool()
def open_document(file_path: str) -> str:
    """지정된 경로의 한글 문서를 엽니다."""
    try:
        hwp_controller.check_initialization()
        
        if not os.path.exists(file_path):
            return f"파일을 찾을 수 없습니다: {file_path}"
        
        try:
            hwp_controller.hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except:
            pass
        
        # 모든 대화상자 자동 처리: 버전 경고, 암호, 접근 권한 등
        result = hwp_controller.hwp.Open(file_path, "HWP", "forceopen:true;versionwarning:false;suspendpassword:true")

        if result:
            hwp_controller.current_document = file_path

            # 한글 창을 화면 제일 앞으로 가져오기
            try:
                hwnd = hwp_controller.hwp.XHwpWindows.Active_XHwpWindow.WindowHandle
                win32gui.SetForegroundWindow(hwnd)
                win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
            except:
                pass

            logger.info(f"문서 열기 완료: {file_path}")
            return f"문서를 열었습니다: {file_path}"
        else:
            hwp_controller.hwp.HAction.GetDefault("FileOpen", hwp_controller.hwp.HParameterSet.HFileOpenSave.HSet)
            hwp_controller.hwp.HParameterSet.HFileOpenSave.filename = file_path
            hwp_controller.hwp.HParameterSet.HFileOpenSave.Format = "HWP"
            hwp_controller.hwp.HAction.Execute("FileOpen", hwp_controller.hwp.HParameterSet.HFileOpenSave.HSet)
            
            hwp_controller.current_document = file_path
            logger.info(f"문서 열기 완료 (대체방법): {file_path}")
            return f"문서를 열었습니다: {file_path}"
        
    except Exception as e:
        logger.error(f"문서 열기 실패: {e}")
        return f"문서 열기 실패: {e}"

@mcp.tool()
def save_document(file_path: Optional[str] = None) -> str:
    """현재 문서를 저장합니다."""
    try:
        hwp_controller.check_initialization()
        
        if file_path:
            act = hwp_controller.hwp.CreateAction("FileSaveAs")
            pset = act.CreateSet()
            pset.SetItem("filename", file_path)
            pset.SetItem("format", "HWP")
            act.Execute(pset)
            
            hwp_controller.current_document = file_path
            logger.info(f"문서 저장 완료: {file_path}")
            return f"문서를 저장했습니다: {file_path}"
        else:
            hwp_controller.hwp.HAction.Run("FileSave")
            logger.info("문서 저장 완료")
            return "문서를 저장했습니다."
            
    except Exception as e:
        logger.error(f"문서 저장 실패: {e}")
        return f"문서 저장 실패: {e}"

@mcp.tool()
def close_document(save_changes: bool = False) -> str:
    """현재 문서를 닫습니다."""
    try:
        hwp_controller.check_initialization()
        
        if save_changes:
            hwp_controller.hwp.HAction.Run("FileSave")
        
        hwp_controller.hwp.HAction.Run("FileClose")
        hwp_controller.current_document = None
        
        logger.info("문서 닫기 완료")
        return "문서를 닫았습니다."
        
    except Exception as e:
        logger.error(f"문서 닫기 실패: {e}")
        return f"문서 닫기 실패: {e}"

@mcp.tool()
def close_all_documents(save_changes: bool = False) -> str:
    """모든 문서를 닫습니다."""
    try:
        hwp_controller.check_initialization()
        
        closed_count = 0
        max_attempts = 100
        
        for _ in range(max_attempts):
            try:
                if hwp_controller.hwp.XHwpDocuments.Count == 0:
                    break
                
                if save_changes:
                    hwp_controller.hwp.HAction.Run("FileSave")
                
                hwp_controller.hwp.XHwpDocuments.Item(0).SetModified(False)
                hwp_controller.hwp.HAction.Run("FileClose")
                closed_count += 1
            except Exception as e:
                logger.warning(f"문서 닫기 중 오류: {e}")
                break
        
        hwp_controller.current_document = None
        
        logger.info(f"모든 문서 닫기 완료: {closed_count}개")
        return f"모든 문서를 닫았습니다. ({closed_count}개)"
        
    except Exception as e:
        logger.error(f"모든 문서 닫기 실패: {e}")
        return f"모든 문서 닫기 실패: {e}"

@mcp.tool()
def quit_hwp() -> str:
    """한글 프로그램을 종료합니다."""
    try:
        hwp_controller.check_initialization()
        
        hwp_controller.hwp.Quit()
        hwp_controller.hwp = None
        hwp_controller.is_initialized = False
        hwp_controller.current_document = None
        
        logger.info("한글 프로그램 종료 완료")
        return "한글 프로그램을 종료했습니다."
        
    except Exception as e:
        logger.error(f"한글 종료 실패: {e}")
        return f"한글 종료 실패: {e}"

@mcp.tool()
def insert_text(text: str, position: str = "current") -> str:
    """텍스트를 삽입합니다."""
    try:
        hwp_controller.check_initialization()
        
        if position == "current":
            act = hwp_controller.hwp.CreateAction("InsertText")
            pset = act.CreateSet()
            pset.SetItem("Text", text)
            act.Execute(pset)
        
        logger.info(f"텍스트 삽입 완료: {text[:50]}...")
        return f"텍스트를 삽입했습니다: {text[:50]}..."
        
    except Exception as e:
        logger.error(f"텍스트 삽입 실패: {e}")
        return f"텍스트 삽입 실패: {e}"

@mcp.tool()
def insert_text_at_position(text: str, x: int = 0, y: int = 0) -> str:
    """지정된 좌표에 텍스트를 삽입합니다."""
    try:
        hwp_controller.check_initialization()
        
        hwp_controller.hwp.SetPosBySet(x, y)
        
        act = hwp_controller.hwp.CreateAction("InsertText")
        pset = act.CreateSet()
        pset.SetItem("Text", text)
        act.Execute(pset)
        
        logger.info(f"위치 ({x}, {y})에 텍스트 삽입 완료")
        return f"위치 ({x}, {y})에 텍스트 '{text}'를 삽입했습니다."
        
    except Exception as e:
        logger.error(f"위치별 텍스트 삽입 실패: {e}")
        return f"위치별 텍스트 삽입 실패: {e}"

@mcp.tool()
def apply_font_format(font_name: str = "맑은 고딕", 
                     font_size: int = 11, 
                     bold: bool = False, 
                     italic: bool = False, 
                     underline: bool = False,
                     color: str = "black") -> str:
    """선택된 텍스트에 글꼴 서식을 적용합니다."""
    try:
        hwp_controller.check_initialization()
        
        color_map = {
            "black": 0x000000,
            "red": 0xFF0000,
            "blue": 0x0000FF,
            "green": 0x00FF00,
            "yellow": 0xFFFF00,
            "purple": 0xFF00FF,
            "cyan": 0x00FFFF
        }
        
        color_value = color_map.get(color.lower(), 0x000000)
        
        act = hwp_controller.hwp.CreateAction("CharShape")
        pset = act.CreateSet()
        pset.SetItem("FaceNameHangul", font_name)
        pset.SetItem("FaceNameLatin", font_name)
        pset.SetItem("FaceNameHanja", font_name)
        pset.SetItem("FaceNameJapanese", font_name)
        pset.SetItem("FaceNameOther", font_name)
        pset.SetItem("FaceNameSymbol", font_name)
        pset.SetItem("FaceNameUser", font_name)
        pset.SetItem("Height", font_size * 100)
        pset.SetItem("Bold", bold)
        pset.SetItem("Italic", italic)
        pset.SetItem("Underline", underline)
        pset.SetItem("TextColor", color_value)
        act.Execute(pset)
        
        logger.info(f"글꼴 서식 적용 완료: {font_name}, {font_size}pt")
        return f"글꼴 서식을 적용했습니다: {font_name}, {font_size}pt"
        
    except Exception as e:
        logger.error(f"글꼴 서식 적용 실패: {e}")
        return f"글꼴 서식 적용 실패: {e}"

@mcp.tool()
def select_text_range(start_pos: int, end_pos: int) -> str:
    """지정된 범위의 텍스트를 선택합니다."""
    try:
        hwp_controller.check_initialization()
        
        hwp_controller.hwp.SetPos(start_pos)
        hwp_controller.hwp.MovePos(2, end_pos - start_pos, 1)
        
        logger.info(f"텍스트 선택 완료: {start_pos} ~ {end_pos}")
        return f"텍스트를 선택했습니다: 위치 {start_pos} ~ {end_pos}"
        
    except Exception as e:
        logger.error(f"텍스트 선택 실패: {e}")
        return f"텍스트 선택 실패: {e}"

@mcp.tool()
def find_and_replace(find_text: str, replace_text: str, replace_all: bool = False) -> str:
    """텍스트를 찾아서 바꿉니다."""
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        # 문서 시작으로 이동
        hwp.HAction.Run("MoveDocBegin")

        # HParameterSet 방식 사용
        if replace_all:
            hwp.HAction.GetDefault("AllReplace", hwp.HParameterSet.HFindReplace.HSet)
            hwp.HParameterSet.HFindReplace.FindString = find_text
            hwp.HParameterSet.HFindReplace.ReplaceString = replace_text
            hwp.HParameterSet.HFindReplace.ReplaceMode = 1  # 모두 바꾸기
            result = hwp.HAction.Execute("AllReplace", hwp.HParameterSet.HFindReplace.HSet)
        else:
            hwp.HAction.GetDefault("Replace", hwp.HParameterSet.HFindReplace.HSet)
            hwp.HParameterSet.HFindReplace.FindString = find_text
            hwp.HParameterSet.HFindReplace.ReplaceString = replace_text
            result = hwp.HAction.Execute("Replace", hwp.HParameterSet.HFindReplace.HSet)

        if result:
            logger.info(f"찾기/바꾸기 완료: '{find_text}' -> '{replace_text}'")
            return f"'{find_text}'를 '{replace_text}'로 {'모두 ' if replace_all else ''}바꾸었습니다."
        else:
            return f"'{find_text}'를 찾을 수 없습니다."

    except Exception as e:
        logger.error(f"찾기/바꾸기 실패: {e}")
        return f"찾기/바꾸기 실패: {e}"

@mcp.tool()
def create_table(rows: int, cols: int, border: bool = True) -> str:
    """표를 생성합니다."""
    try:
        hwp_controller.check_initialization()
        
        act = hwp_controller.hwp.CreateAction("TableCreate")
        pset = act.CreateSet()
        pset.SetItem("Rows", rows)
        pset.SetItem("Cols", cols)
        pset.SetItem("WidthType", 2)
        pset.SetItem("HeightType", 0)
        pset.SetItem("CreateItemArray", [0, 1, 0])
        act.Execute(pset)
        
        logger.info(f"표 생성 완료: {rows}행 {cols}열")
        return f"{rows}행 {cols}열 표를 생성했습니다."
        
    except Exception as e:
        logger.error(f"표 생성 실패: {e}")
        return f"표 생성 실패: {e}"

@mcp.tool()
def set_page_margins(top: int = 20, bottom: int = 20, left: int = 20, right: int = 20) -> str:
    """페이지 여백을 설정합니다. (단위: mm)"""
    try:
        hwp_controller.check_initialization()
        
        act = hwp_controller.hwp.CreateAction("PageSetup")
        pset = act.CreateSet()
        pset.SetItem("TopMargin", top * 100)
        pset.SetItem("BottomMargin", bottom * 100)
        pset.SetItem("LeftMargin", left * 100)
        pset.SetItem("RightMargin", right * 100)
        act.Execute(pset)
        
        logger.info(f"페이지 여백 설정 완료: 상{top} 하{bottom} 좌{left} 우{right}mm")
        return f"페이지 여백을 설정했습니다: 상{top} 하{bottom} 좌{left} 우{right}mm"
        
    except Exception as e:
        logger.error(f"페이지 여백 설정 실패: {e}")
        return f"페이지 여백 설정 실패: {e}"

@mcp.tool()
def get_document_info() -> str:
    """현재 문서의 정보를 조회합니다."""
    try:
        hwp_controller.check_initialization()
        
        try:
            page_count = hwp_controller.hwp.PageCount
        except:
            page_count = "Unknown"
            
        try:
            current_pos = hwp_controller.hwp.GetPos()
        except:
            current_pos = "Unknown"
            
        try:
            list_count = getattr(hwp_controller.hwp, 'ListCount', 0)
        except:
            list_count = "Unknown"
        
        info = {
            "page_count": page_count,
            "current_pos": current_pos,
            "list_count": list_count,
            "document_name": hwp_controller.current_document or "새 문서"
        }
        
        result = f"""문서 정보:
- 문서명: {info['document_name']}
- 총 페이지 수: {info['page_count']}
- 현재 커서 위치: {info['current_pos']}
- 리스트 개수: {info['list_count']}"""
        
        logger.info("문서 정보 조회 완료")
        return result
        
    except Exception as e:
        logger.error(f"문서 정보 조회 실패: {e}")
        return f"문서 정보 조회 실패: {e}"

@mcp.tool()
def set_paragraph_format(align: str = "left", 
                        left_indent: int = 0, 
                        right_indent: int = 0, 
                        line_spacing: float = 1.0) -> str:
    """문단 서식을 설정합니다."""
    try:
        hwp_controller.check_initialization()
        
        align_map = {
            "left": 0,
            "center": 1,
            "right": 2,
            "justify": 3,
            "distribute": 4
        }
        
        align_value = align_map.get(align.lower(), 0)
        
        act = hwp_controller.hwp.CreateAction("ParagraphShape")
        pset = act.CreateSet()
        pset.SetItem("Align", align_value)
        pset.SetItem("IndentLeft", left_indent * 100)
        pset.SetItem("IndentRight", right_indent * 100)
        pset.SetItem("LineSpacing", int(line_spacing * 100))
        act.Execute(pset)
        
        logger.info(f"문단 서식 설정 완료: {align} 정렬, 줄간격 {line_spacing}")
        return f"문단 서식을 설정했습니다: {align} 정렬, 줄간격 {line_spacing}"
        
    except Exception as e:
        logger.error(f"문단 서식 설정 실패: {e}")
        return f"문단 서식 설정 실패: {e}"

@mcp.tool()
def set_page_size(width: int = 210, height: int = 297, orientation: str = "portrait") -> str:
    """용지 크기와 방향을 설정합니다. (단위: mm)"""
    try:
        hwp_controller.check_initialization()
        
        if orientation.lower() == "landscape":
            width, height = height, width
        
        act = hwp_controller.hwp.CreateAction("PageSetup")
        pset = act.CreateSet()
        pset.SetItem("Width", width * 100)
        pset.SetItem("Height", height * 100)
        pset.SetItem("Orientation", 1 if orientation.lower() == "landscape" else 0)
        act.Execute(pset)
        
        logger.info(f"용지 설정 완료: {width}x{height}mm, {orientation}")
        return f"용지를 설정했습니다: {width}x{height}mm, {orientation}"
        
    except Exception as e:
        logger.error(f"용지 설정 실패: {e}")
        return f"용지 설정 실패: {e}"

@mcp.tool()
def insert_image(image_path: str, x: int = 0, y: int = 0, width: int = 100, height: int = 100) -> str:
    """이미지를 삽입합니다."""
    try:
        hwp_controller.check_initialization()
        
        if not os.path.exists(image_path):
            return f"이미지 파일을 찾을 수 없습니다: {image_path}"
        
        act = hwp_controller.hwp.CreateAction("InsertPicture")
        pset = act.CreateSet()
        pset.SetItem("Path", image_path)
        pset.SetItem("Embedded", True)
        pset.SetItem("sizeoption", 3)
        pset.SetItem("Width", width * 100)
        pset.SetItem("Height", height * 100)
        act.Execute(pset)
        
        logger.info(f"이미지 삽입 완료: {image_path}")
        return f"이미지를 삽입했습니다: {image_path}"
        
    except Exception as e:
        logger.error(f"이미지 삽입 실패: {e}")
        return f"이미지 삽입 실패: {e}"

@mcp.tool()
def insert_shape(shape_type: str, x: int = 0, y: int = 0, width: int = 50, height: int = 50) -> str:
    """도형을 삽입합니다."""
    try:
        hwp_controller.check_initialization()
        
        shape_map = {
            "rectangle": 1,
            "ellipse": 2,
            "line": 3,
            "arrow": 4,
            "textbox": 5
        }
        
        shape_value = shape_map.get(shape_type.lower(), 1)
        
        act = hwp_controller.hwp.CreateAction("DrawObjDialog")
        pset = act.CreateSet()
        pset.SetItem("ShapeType", shape_value)
        pset.SetItem("TreatAsChar", False)
        act.Execute(pset)
        
        logger.info(f"도형 삽입 완료: {shape_type}")
        return f"도형을 삽입했습니다: {shape_type}"
        
    except Exception as e:
        logger.error(f"도형 삽입 실패: {e}")
        return f"도형 삽입 실패: {e}"

@mcp.tool()
def insert_header_footer(text: str, is_header: bool = True, position: str = "center") -> str:
    """머리글 또는 바닥글을 삽입합니다."""
    try:
        hwp_controller.check_initialization()
        
        if is_header:
            hwp_controller.hwp.HAction.Run("HeaderFooterEdit")
        else:
            hwp_controller.hwp.HAction.Run("HeaderFooterEdit")
        
        act = hwp_controller.hwp.CreateAction("InsertText")
        pset = act.CreateSet()
        pset.SetItem("Text", text)
        act.Execute(pset)
        
        hwp_controller.hwp.HAction.Run("CloseEx")
        
        logger.info(f"{'머리글' if is_header else '바닥글'} 삽입 완료")
        return f"{'머리글' if is_header else '바닥글'}을 삽입했습니다: {text}"
        
    except Exception as e:
        logger.error(f"머리글/바닥글 삽입 실패: {e}")
        return f"머리글/바닥글 삽입 실패: {e}"

@mcp.tool()
def insert_page_break() -> str:
    """페이지 나누기를 삽입합니다."""
    try:
        hwp_controller.check_initialization()
        
        act = hwp_controller.hwp.CreateAction("BreakPage")
        act.Execute()
        
        logger.info("페이지 나누기 삽입 완료")
        return "페이지 나누기를 삽입했습니다."
        
    except Exception as e:
        logger.error(f"페이지 나누기 삽입 실패: {e}")
        return f"페이지 나누기 삽입 실패: {e}"

@mcp.tool()
def merge_table_cells(start_row: int, start_col: int, end_row: int, end_col: int) -> str:
    """표의 셀을 병합합니다."""
    try:
        hwp_controller.check_initialization()
        
        hwp_controller.hwp.TableCellBlock(start_row, start_col, end_row, end_col)
        
        act = hwp_controller.hwp.CreateAction("TableMergeCell")
        act.Execute()
        
        logger.info(f"셀 병합 완료: ({start_row},{start_col}) ~ ({end_row},{end_col})")
        return f"셀을 병합했습니다: ({start_row},{start_col}) ~ ({end_row},{end_col})"
        
    except Exception as e:
        logger.error(f"셀 병합 실패: {e}")
        return f"셀 병합 실패: {e}"

@mcp.tool()
def insert_hyperlink(text: str, url: str) -> str:
    """하이퍼링크를 삽입합니다."""
    try:
        hwp_controller.check_initialization()
        
        act = hwp_controller.hwp.CreateAction("InsertHyperlink")
        pset = act.CreateSet()
        pset.SetItem("Text", text)
        pset.SetItem("URL", url)
        act.Execute(pset)
        
        logger.info(f"하이퍼링크 삽입 완료: {text} -> {url}")
        return f"하이퍼링크를 삽입했습니다: {text} -> {url}"
        
    except Exception as e:
        logger.error(f"하이퍼링크 삽입 실패: {e}")
        return f"하이퍼링크 삽입 실패: {e}"

@mcp.tool()
def create_table_of_contents() -> str:
    """목차를 생성합니다."""
    try:
        hwp_controller.check_initialization()
        
        act = hwp_controller.hwp.CreateAction("InsertTableOfContents")
        pset = act.CreateSet()
        pset.SetItem("AutoUpdate", True)
        pset.SetItem("ShowPageNum", True)
        act.Execute(pset)
        
        logger.info("목차 생성 완료")
        return "목차를 생성했습니다."
        
    except Exception as e:
        logger.error(f"목차 생성 실패: {e}")
        return f"목차 생성 실패: {e}"

@mcp.tool()
def apply_heading_style(level: int, text: str) -> str:
    """제목 스타일을 적용합니다."""
    try:
        hwp_controller.check_initialization()
        
        act = hwp_controller.hwp.CreateAction("InsertText")
        pset = act.CreateSet()
        pset.SetItem("Text", text)
        act.Execute(pset)
        
        style_name = f"제목 {level}"
        act = hwp_controller.hwp.CreateAction("StyleApply")
        pset = act.CreateSet()
        pset.SetItem("StyleName", style_name)
        act.Execute(pset)
        
        logger.info(f"제목 스타일 적용 완료: {style_name}")
        return f"제목 스타일을 적용했습니다: {style_name}"
        
    except Exception as e:
        logger.error(f"제목 스타일 적용 실패: {e}")
        return f"제목 스타일 적용 실패: {e}"

@mcp.tool()
def export_to_pdf(output_path: str) -> str:
    """현재 문서를 PDF로 내보냅니다."""
    try:
        hwp_controller.check_initialization()
        
        act = hwp_controller.hwp.CreateAction("FileSaveAsPdf")
        pset = act.CreateSet()
        pset.SetItem("filename", output_path)
        pset.SetItem("Format", "PDF")
        act.Execute(pset)
        
        logger.info(f"PDF 내보내기 완료: {output_path}")
        return f"PDF로 내보냈습니다: {output_path}"
        
    except Exception as e:
        logger.error(f"PDF 내보내기 실패: {e}")
        return f"PDF 내보내기 실패: {e}"

@mcp.tool()
def get_text_all() -> str:
    """문서 전체의 텍스트를 읽어옵니다."""
    try:
        hwp_controller.check_initialization()

        hwp_controller.hwp.HAction.Run("SelectAll")
        text = hwp_controller.hwp.GetTextFile("TEXT", "")
        hwp_controller.hwp.HAction.Run("MoveDocBegin")

        if text is None:
            text = ""

        logger.info(f"전체 텍스트 읽기 완료: {len(text)} 글자")
        return text
        
    except Exception as e:
        logger.error(f"텍스트 읽기 실패: {e}")
        return f"텍스트 읽기 실패: {e}"

@mcp.tool()
def get_text_by_page(page_number: int) -> str:
    """특정 페이지의 텍스트를 읽어옵니다."""
    try:
        hwp_controller.check_initialization()

        hwp_controller.hwp.HAction.GetDefault("Goto", hwp_controller.hwp.HParameterSet.HGotoE.HSet)
        hwp_controller.hwp.HParameterSet.HGotoE.PageNumber = page_number
        hwp_controller.hwp.HAction.Execute("Goto", hwp_controller.hwp.HParameterSet.HGotoE.HSet)

        hwp_controller.hwp.HAction.Run("MovePageBegin")
        hwp_controller.hwp.HAction.Run("MoveSelPageDown")

        text = hwp_controller.hwp.GetTextFile("TEXT", "")
        hwp_controller.hwp.HAction.Run("Cancel")

        if text is None:
            text = ""

        logger.info(f"{page_number}페이지 텍스트 읽기 완료")
        return text
        
    except Exception as e:
        logger.error(f"페이지 텍스트 읽기 실패: {e}")
        return f"페이지 텍스트 읽기 실패: {e}"

@mcp.tool()
def get_selected_text() -> str:
    """현재 선택된 텍스트를 읽어옵니다."""
    try:
        hwp_controller.check_initialization()

        text = hwp_controller.hwp.GetTextFile("TEXT", "")

        if text is None:
            text = ""

        logger.info(f"선택된 텍스트 읽기 완료: {len(text)} 글자")
        return text
        
    except Exception as e:
        logger.error(f"선택된 텍스트 읽기 실패: {e}")
        return f"선택된 텍스트 읽기 실패: {e}"

@mcp.tool()
def get_paragraph_text(paragraph_index: int = 0) -> str:
    """특정 문단의 텍스트를 읽어옵니다. (0부터 시작)"""
    try:
        hwp_controller.check_initialization()

        hwp_controller.hwp.HAction.Run("MoveDocBegin")

        for _ in range(paragraph_index):
            hwp_controller.hwp.HAction.Run("MoveParaDown")

        hwp_controller.hwp.HAction.Run("MoveSelParaDown")
        text = hwp_controller.hwp.GetTextFile("TEXT", "")
        hwp_controller.hwp.HAction.Run("Cancel")

        if text is None:
            text = ""

        logger.info(f"{paragraph_index}번째 문단 텍스트 읽기 완료")
        return text.strip()
        
    except Exception as e:
        logger.error(f"문단 텍스트 읽기 실패: {e}")
        return f"문단 텍스트 읽기 실패: {e}"

@mcp.tool()
def save_as_text(output_path: str) -> str:
    """문서 전체를 텍스트 파일로 저장합니다."""
    try:
        hwp_controller.check_initialization()
        
        hwp_controller.hwp.SaveAs(output_path, "TEXT")
        
        logger.info(f"텍스트 파일로 저장 완료: {output_path}")
        return f"텍스트 파일로 저장했습니다: {output_path}"
        
    except Exception as e:
        logger.error(f"텍스트 저장 실패: {e}")
        return f"텍스트 저장 실패: {e}"


# ============================================================
# 고급 분석 및 자동화 기능
# ============================================================

@mcp.tool()
def get_table_as_csv(table_index: int = 1, output_path: Optional[str] = None) -> str:
    """
    특정 표를 CSV 형식으로 추출합니다. (1부터 시작)
    output_path를 지정하면 파일로 저장, 아니면 텍스트로 반환합니다.
    """
    try:
        hwp_controller.check_initialization()
        
        hwp = hwp_controller.hwp
        current_table = 0
        
        hwp.HAction.Run("MoveDocBegin")
        
        ctrl = hwp.HeadCtrl
        target_ctrl = None
        
        while ctrl:
            try:
                if ctrl.CtrlID == 'tbl':
                    current_table += 1
                    if current_table == table_index:
                        target_ctrl = ctrl
                        break
                ctrl = ctrl.Next
            except:
                break
        
        if not target_ctrl:
            return f"{table_index}번째 표를 찾을 수 없습니다. (총 {current_table}개 표 존재)"
        
        rows = 0
        cols = 0
        try:
            tbl_set = target_ctrl.Properties
            rows = tbl_set.Item("RowCount")
            cols = tbl_set.Item("ColCount")
        except:
            pass
        
        cell_contents = []
        try:
            hwp.SetPosBySet(target_ctrl.GetAnchorPos(0))
            hwp.HAction.Run("ShapeObjTableSelCell")
            hwp.HAction.Run("TableColBegin")
            hwp.HAction.Run("TableRowBegin")
            hwp.HAction.Run("TableCellBlockExtendAll")
            
            table_text = hwp.GetTextFile("TEXT", "")

            if table_text is None:
                table_text = ""

            if table_text:
                cell_contents = [t.strip() for t in table_text.split('\r\n') if t.strip()]
            
            hwp.HAction.Run("Cancel")
            
        except Exception as e:
            logger.warning(f"표 내용 추출 중 오류: {e}")
            return f"표 내용 추출 실패: {e}"
        
        csv_lines = []
        if rows > 0 and cols > 0 and len(cell_contents) >= rows * cols:
            for r in range(rows):
                row_data = []
                for c in range(cols):
                    idx = r * cols + c
                    if idx < len(cell_contents):
                        cell = cell_contents[idx].replace('"', '""')
                        if ',' in cell or '"' in cell or '\n' in cell:
                            cell = f'"{cell}"'
                        row_data.append(cell)
                csv_lines.append(','.join(row_data))
        else:
            for cell in cell_contents:
                cell = cell.replace('"', '""')
                if ',' in cell or '"' in cell:
                    cell = f'"{cell}"'
                csv_lines.append(cell)
        
        csv_content = '\n'.join(csv_lines)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8-sig') as f:
                f.write(csv_content)
            logger.info(f"표 {table_index} CSV 저장 완료: {output_path}")
            return f"표 {table_index}을(를) CSV로 저장했습니다: {output_path}\n({rows}행 x {cols}열, {len(cell_contents)}개 셀)"
        else:
            logger.info(f"표 {table_index} CSV 추출 완료")
            return f"표 {table_index} CSV 내용 ({rows}행 x {cols}열):\n\n{csv_content}"
        
    except Exception as e:
        logger.error(f"표 CSV 추출 실패: {e}")
        return f"표 CSV 추출 실패: {e}"


@mcp.tool()
def batch_replace(replacements: str) -> str:
    """
    여러 텍스트를 한번에 바꿉니다.
    replacements: "찾을텍스트1->바꿀텍스트1, 찾을텍스트2->바꿀텍스트2" 형식
    예: "주식회사->㈜, 2023년->2024년, 홍길동->김철수"
    """
    try:
        hwp_controller.check_initialization()
        
        hwp = hwp_controller.hwp
        
        pairs = [p.strip() for p in replacements.split(',')]
        results = []
        total_replaced = 0
        
        for pair in pairs:
            if '->' not in pair:
                results.append(f"! '{pair}': 잘못된 형식 (->로 구분 필요)")
                continue
            
            parts = pair.split('->', 1)
            find_text = parts[0].strip()
            replace_text = parts[1].strip()
            
            if not find_text:
                results.append(f"! 빈 검색어는 건너뜁니다")
                continue
            
            hwp.HAction.Run("MoveDocBegin")

            hwp.HAction.GetDefault("AllReplace", hwp.HParameterSet.HFindReplace.HSet)
            hwp.HParameterSet.HFindReplace.FindString = find_text
            hwp.HParameterSet.HFindReplace.ReplaceString = replace_text
            hwp.HParameterSet.HFindReplace.ReplaceMode = 1

            execute_result = hwp.HAction.Execute("AllReplace", hwp.HParameterSet.HFindReplace.HSet)
            
            if execute_result:
                results.append(f"O '{find_text}' -> '{replace_text}': 완료")
                total_replaced += 1
            else:
                results.append(f"- '{find_text}': 찾을 수 없음")
        
        result = f"""일괄 바꾸기 결과
==============================
총 {len(pairs)}개 항목 중 {total_replaced}개 처리 완료

"""
        result += '\n'.join(results)
        
        logger.info(f"일괄 바꾸기 완료: {total_replaced}/{len(pairs)}개")
        return result
        
    except Exception as e:
        logger.error(f"일괄 바꾸기 실패: {e}")
        return f"일괄 바꾸기 실패: {e}"


@mcp.tool()
def find_text(search_text: str, show_context: bool = True) -> str:
    """
    문서에서 특정 텍스트를 찾아 위치와 주변 내용을 반환합니다.
    search_text: 찾을 텍스트
    show_context: True면 주변 텍스트도 함께 표시
    """
    try:
        hwp_controller.check_initialization()
        
        hwp = hwp_controller.hwp
        
        hwp.HAction.Run("SelectAll")
        full_text = hwp.GetTextFile("TEXT", "")
        hwp.HAction.Run("MoveDocBegin")

        if full_text is None:
            full_text = ""

        if not full_text:
            return "문서에 내용이 없습니다."
        
        search_lower = search_text.lower()
        text_lower = full_text.lower()
        
        positions = []
        start = 0
        while True:
            pos = text_lower.find(search_lower, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1
        
        if not positions:
            return f"'{search_text}'을(를) 찾을 수 없습니다."
        
        lines = full_text.split('\r\n')
        results = []
        
        for i, pos in enumerate(positions, 1):
            current_pos = 0
            line_num = 0
            
            for idx, line in enumerate(lines):
                line_end = current_pos + len(line)
                if current_pos <= pos < line_end + 2:
                    line_num = idx + 1
                    break
                current_pos = line_end + 2
            
            estimated_page = (line_num // 50) + 1
            
            if show_context:
                context_start = max(0, pos - 50)
                context_end = min(len(full_text), pos + len(search_text) + 50)
                context = full_text[context_start:context_end].replace('\r\n', ' ')
                
                highlight_pos = pos - context_start
                context_display = (
                    context[:highlight_pos] + 
                    f"[{search_text}]" + 
                    context[highlight_pos + len(search_text):]
                )
                
                results.append(f"  [{i}] {line_num}번째 줄 (약 {estimated_page}페이지)\n      ...{context_display}...")
            else:
                results.append(f"  [{i}] {line_num}번째 줄 (약 {estimated_page}페이지)")
        
        result = f"""검색 결과: '{search_text}'
==============================
총 {len(positions)}개 발견

"""
        result += '\n\n'.join(results)
        
        logger.info(f"텍스트 검색 완료: '{search_text}' - {len(positions)}개 발견")
        return result
        
    except Exception as e:
        logger.error(f"텍스트 검색 실패: {e}")
        return f"텍스트 검색 실패: {e}"


@mcp.tool()
def fill_template(field_values: str) -> str:
    """
    문서의 필드(플레이스홀더)를 값으로 채웁니다.
    필드는 {{필드명}} 또는 {필드명} 형식으로 문서에 있어야 합니다.
    
    field_values: "필드명1=값1, 필드명2=값2" 형식
    예: "이름=홍길동, 날짜=2024-01-01, 금액=1,000,000원"
    """
    try:
        hwp_controller.check_initialization()
        
        hwp = hwp_controller.hwp
        
        pairs = [p.strip() for p in field_values.split(',')]
        results = []
        total_filled = 0
        
        for pair in pairs:
            if '=' not in pair:
                results.append(f"! '{pair}': 잘못된 형식 (=로 구분 필요)")
                continue
            
            parts = pair.split('=', 1)
            field_name = parts[0].strip()
            field_value = parts[1].strip()
            
            if not field_name:
                results.append(f"! 빈 필드명은 건너뜁니다")
                continue
            
            placeholders = [
                "{{" + field_name + "}}",
                "{" + field_name + "}",
                "[" + field_name + "]",
                "<" + field_name + ">",
                "$" + field_name + "$",
                field_name
            ]
            
            replaced = False
            for placeholder in placeholders:
                hwp.HAction.Run("MoveDocBegin")
                
                hwp.HAction.GetDefault("AllReplace", hwp.HParameterSet.HFindReplace.HSet)
                hwp.HParameterSet.HFindReplace.FindString = placeholder
                hwp.HParameterSet.HFindReplace.ReplaceString = field_value
                hwp.HParameterSet.HFindReplace.ReplaceMode = 1
                
                execute_result = hwp.HAction.Execute("AllReplace", hwp.HParameterSet.HFindReplace.HSet)
                
                if execute_result:
                    results.append(f"O {placeholder} -> '{field_value}': 완료")
                    total_filled += 1
                    replaced = True
                    break
            
            if not replaced:
                results.append(f"- '{field_name}': 해당 필드를 찾을 수 없음")
        
        result = f"""템플릿 채우기 결과
==============================
총 {len(pairs)}개 필드 중 {total_filled}개 채움 완료

"""
        result += '\n'.join(results)
        
        if total_filled < len(pairs):
            result += "\n\n팁: 문서에서 필드는 {{이름}}, {이름}, [이름] 등의 형식으로 작성해주세요."
        
        logger.info(f"템플릿 채우기 완료: {total_filled}/{len(pairs)}개")
        return result
        
    except Exception as e:
        logger.error(f"템플릿 채우기 실패: {e}")
        return f"템플릿 채우기 실패: {e}"


@mcp.tool()
def get_document_structure() -> str:
    """
    문서의 전체 구조를 분석합니다. (페이지 수, 문단 수, 표 개수, 이미지 개수, 제목/개요 구조)
    """
    try:
        hwp_controller.check_initialization()
        
        hwp = hwp_controller.hwp
        
        page_count = hwp.PageCount
        
        doc_path = "(새 문서)"
        try:
            if hwp.XHwpDocuments.Count > 0:
                active_doc = hwp.XHwpDocuments.Item(0)
                if active_doc.Path:
                    doc_path = active_doc.Path
        except:
            pass
        
        doc_name = doc_path.split("\\")[-1] if doc_path != "(새 문서)" else "새 문서"
        
        hwp.HAction.Run("SelectAll")
        full_text = hwp.GetTextFile("TEXT", "")
        hwp.HAction.Run("MoveDocBegin")

        if full_text is None:
            full_text = ""

        char_count = len(full_text.replace('\r\n', '').replace(' ', '')) if full_text else 0
        paragraph_count = full_text.count('\r\n') + 1 if full_text else 0
        
        table_count = 0
        image_count = 0
        shape_count = 0
        
        ctrl = hwp.HeadCtrl
        while ctrl:
            try:
                ctrl_code = ctrl.CtrlID
                if ctrl_code == 'tbl':
                    table_count += 1
                elif ctrl_code in ['ole', 'pic']:
                    image_count += 1
                elif ctrl_code == 'gso':
                    shape_count += 1
                ctrl = ctrl.Next
            except:
                break
        
        headings = []
        lines = full_text.split('\r\n') if full_text else []
        
        heading_patterns = [
            (r'^\s*([IVX]+)\.\s*(.+)$', 1, "로마자"),
            (r'^\s*(\d+)\.\s*(.+)$', 2, "숫자"),
            (r'^\s*([가-힣])\.\s*(.+)$', 3, "가나다"),
            (r'^\s*\((\d+)\)\s*(.+)$', 3, "괄호숫자"),
            (r'^\s*(제\s*\d+\s*[장절조항])\s*(.*)$', 1, "장절"),
            (r'^\s*(붙임|별첨|부록)\s*[\d]*\.?\s*(.*)$', 1, "붙임"),
        ]
        
        for i, line in enumerate(lines[:200]):
            line_stripped = line.strip()
            if not line_stripped or len(line_stripped) > 100:
                continue
            
            for pattern, level, ptype in heading_patterns:
                if re.match(pattern, line_stripped):
                    headings.append({
                        "line": i + 1,
                        "level": level,
                        "text": line_stripped[:60] + ("..." if len(line_stripped) > 60 else ""),
                        "type": ptype
                    })
                    break
        
        result = f"""문서 구조 분석 결과
{'='*50}

기본 정보:
  - 파일명: {doc_name}
  - 총 페이지: {page_count}페이지
  - 총 문단: {paragraph_count}개 (추정)
  - 총 글자: {char_count:,}자 (공백 제외)

포함된 요소:
  - 표(테이블): {table_count}개
  - 이미지/그림: {image_count}개
  - 도형: {shape_count}개
"""
        
        if headings:
            result += f"\n문서 개요 구조 ({len(headings)}개 항목):\n"
            for h in headings[:20]:
                indent = "  " * h['level']
                result += f"{indent}- {h['text']}\n"
            if len(headings) > 20:
                result += f"  ... 외 {len(headings) - 20}개 항목\n"
        else:
            result += "\n문서 개요: (번호 체계 없음)\n"
        
        result += f"\n{'='*50}"
        
        logger.info(f"문서 구조 분석 완료: {doc_name}")
        return result
        
    except Exception as e:
        logger.error(f"문서 구조 분석 실패: {e}")
        return f"문서 구조 분석 실패: {e}"


# ============================================================
# 개선된 위치 제어 및 편집 기능
# ============================================================

@mcp.tool()
def move_to_page(page_number: int) -> str:
    """
    특정 페이지로 커서를 이동합니다.
    page_number: 이동할 페이지 번호 (1부터 시작)
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        total_pages = hwp.PageCount
        if page_number < 1 or page_number > total_pages:
            return f"페이지 번호가 범위를 벗어났습니다. (1~{total_pages})"

        hwp.HAction.GetDefault("Goto", hwp.HParameterSet.HGotoE.HSet)
        hwp.HParameterSet.HGotoE.PageNumber = page_number
        hwp.HAction.Execute("Goto", hwp.HParameterSet.HGotoE.HSet)

        logger.info(f"{page_number}페이지로 이동 완료")
        return f"{page_number}페이지로 이동했습니다."

    except Exception as e:
        logger.error(f"페이지 이동 실패: {e}")
        return f"페이지 이동 실패: {e}"


@mcp.tool()
def move_to_paragraph_number(paragraph_number: int) -> str:
    """
    특정 문단으로 커서를 이동합니다. (0부터 시작)
    paragraph_number: 이동할 문단 번호
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        hwp.HAction.Run("MoveDocBegin")

        for i in range(paragraph_number):
            hwp.HAction.Run("MoveParaDown")

        logger.info(f"{paragraph_number}번째 문단으로 이동 완료")
        return f"{paragraph_number}번째 문단으로 이동했습니다."

    except Exception as e:
        logger.error(f"문단 이동 실패: {e}")
        return f"문단 이동 실패: {e}"


@mcp.tool()
def move_to_document_end() -> str:
    """문서의 끝으로 커서를 이동합니다."""
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        hwp.HAction.Run("MoveDocEnd")

        logger.info("문서 끝으로 이동 완료")
        return "문서 끝으로 이동했습니다."

    except Exception as e:
        logger.error(f"문서 끝 이동 실패: {e}")
        return f"문서 끝 이동 실패: {e}"


@mcp.tool()
def move_to_document_start() -> str:
    """문서의 시작으로 커서를 이동합니다."""
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        hwp.HAction.Run("MoveDocBegin")

        logger.info("문서 시작으로 이동 완료")
        return "문서 시작으로 이동했습니다."

    except Exception as e:
        logger.error(f"문서 시작 이동 실패: {e}")
        return f"문서 시작 이동 실패: {e}"


# ============================================================
# 텍스트 삭제 기능
# ============================================================

@mcp.tool()
def delete_selected_text() -> str:
    """현재 선택된 텍스트를 삭제합니다."""
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        # 선택된 텍스트 확인
        selected_text = hwp.GetTextFile("TEXT", "")
        if selected_text is None:
            selected_text = ""

        if not selected_text:
            return "선택된 텍스트가 없습니다."

        # Delete 키 실행
        hwp.HAction.Run("Delete")

        logger.info(f"선택된 텍스트 삭제 완료: {len(selected_text)}자")
        return f"선택된 텍스트를 삭제했습니다. ({len(selected_text)}자)"

    except Exception as e:
        logger.error(f"선택 텍스트 삭제 실패: {e}")
        return f"선택 텍스트 삭제 실패: {e}"


@mcp.tool()
def delete_all_occurrences(text: str) -> str:
    """
    문서에서 특정 텍스트를 모두 찾아서 삭제합니다.
    text: 삭제할 텍스트
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        if not text:
            return "삭제할 텍스트를 지정해주세요."

        # find_and_replace의 로직을 사용하여 모두 삭제
        hwp.HAction.Run("MoveDocBegin")

        hwp.HAction.GetDefault("AllReplace", hwp.HParameterSet.HFindReplace.HSet)
        hwp.HParameterSet.HFindReplace.FindString = text
        hwp.HParameterSet.HFindReplace.ReplaceString = ""
        hwp.HParameterSet.HFindReplace.ReplaceMode = 1  # 모두 바꾸기

        result = hwp.HAction.Execute("AllReplace", hwp.HParameterSet.HFindReplace.HSet)

        if result:
            logger.info(f"'{text}' 모두 삭제 완료")
            return f"'{text}'를 모두 삭제했습니다."
        else:
            return f"'{text}'를 찾을 수 없습니다."

    except Exception as e:
        logger.error(f"텍스트 삭제 실패: {e}")
        return f"텍스트 삭제 실패: {e}"


@mcp.tool()
def delete_current_line() -> str:
    """현재 커서가 있는 줄 전체를 삭제합니다."""
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        # 줄 시작으로 이동
        hwp.HAction.Run("MoveLineBegin")
        # 줄 끝까지 선택
        hwp.HAction.Run("MoveSelLineEnd")
        # 삭제
        hwp.HAction.Run("Delete")
        # 줄바꿈도 삭제 (다음 줄과 합쳐짐)
        hwp.HAction.Run("Delete")

        logger.info("현재 줄 삭제 완료")
        return f"현재 줄을 삭제했습니다."

    except Exception as e:
        logger.error(f"줄 삭제 실패: {e}")
        return f"줄 삭제 실패: {e}"


@mcp.tool()
def delete_current_paragraph() -> str:
    """현재 커서가 있는 문단 전체를 삭제합니다."""
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        # 문단 선택
        hwp.HAction.Run("MoveSelParaDown")
        # 삭제
        hwp.HAction.Run("Delete")

        logger.info("현재 문단 삭제 완료")
        return "현재 문단을 삭제했습니다."

    except Exception as e:
        logger.error(f"문단 삭제 실패: {e}")
        return f"문단 삭제 실패: {e}"


@mcp.tool()
def delete_page_content(page_number: int) -> str:
    """
    특정 페이지의 모든 내용을 삭제합니다.
    page_number: 삭제할 페이지 번호 (1부터 시작)
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        total_pages = hwp.PageCount
        if page_number < 1 or page_number > total_pages:
            return f"페이지 번호가 범위를 벗어났습니다. (1~{total_pages})"

        # 페이지로 이동
        hwp.HAction.GetDefault("Goto", hwp.HParameterSet.HGotoE.HSet)
        hwp.HParameterSet.HGotoE.PageNumber = page_number
        hwp.HAction.Execute("Goto", hwp.HParameterSet.HGotoE.HSet)

        # 페이지 시작으로 이동
        hwp.HAction.Run("MovePageBegin")
        # 페이지 전체 선택
        hwp.HAction.Run("MoveSelPageDown")
        # 삭제
        hwp.HAction.Run("Delete")

        logger.info(f"{page_number}페이지 내용 삭제 완료")
        return f"{page_number}페이지의 내용을 삭제했습니다."

    except Exception as e:
        logger.error(f"페이지 삭제 실패: {e}")
        return f"페이지 삭제 실패: {e}"


# ============================================================
# 서식 유지 및 가져오기 기능
# ============================================================

@mcp.tool()
def get_current_char_shape() -> str:
    """
    현재 커서 위치의 글자 서식 정보를 가져옵니다.
    (글꼴, 크기, 굵기, 기울임, 밑줄, 색상 등)
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        # CharShape 정보 가져오기
        pset = hwp.HParameterSet.HCharShape
        hwp.HAction.GetDefault("CharShape", pset.HSet)

        # 서식 정보 추출 (직접 속성 접근)
        try:
            font_name = pset.FaceNameHangul if hasattr(pset, 'FaceNameHangul') and pset.FaceNameHangul else "알 수 없음"
        except:
            font_name = "알 수 없음"

        try:
            font_size = pset.Height // 100 if hasattr(pset, 'Height') and pset.Height else 0
        except:
            font_size = 0

        try:
            is_bold = bool(pset.Bold) if hasattr(pset, 'Bold') else False
        except:
            is_bold = False

        try:
            is_italic = bool(pset.Italic) if hasattr(pset, 'Italic') else False
        except:
            is_italic = False

        try:
            is_underline = bool(pset.Underline) if hasattr(pset, 'Underline') else False
        except:
            is_underline = False

        try:
            text_color = pset.TextColor if hasattr(pset, 'TextColor') else 0x000000
        except:
            text_color = 0x000000

        # 색상을 RGB로 변환
        r = text_color & 0xFF
        g = (text_color >> 8) & 0xFF
        b = (text_color >> 16) & 0xFF

        result = f"""현재 위치의 글자 서식:
- 글꼴: {font_name}
- 크기: {font_size}pt
- 굵게: {'예' if is_bold else '아니오'}
- 기울임: {'예' if is_italic else '아니오'}
- 밑줄: {'예' if is_underline else '아니오'}
- 색상: RGB({r}, {g}, {b})"""

        logger.info("글자 서식 정보 조회 완료")
        return result

    except Exception as e:
        logger.error(f"서식 정보 조회 실패: {e}")
        return f"서식 정보 조회 실패: {e}"


@mcp.tool()
def insert_text_preserving_format(text: str) -> str:
    """
    현재 위치의 서식을 유지하면서 텍스트를 삽입합니다.
    한글의 기본 동작이 서식을 유지하므로, 단순 삽입으로 동작합니다.
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        # 한글은 기본적으로 현재 위치의 서식을 유지하면서 텍스트를 삽입함
        act = hwp.CreateAction("InsertText")
        pset = act.CreateSet()
        pset.SetItem("Text", text)
        act.Execute(pset)

        logger.info(f"서식 유지 텍스트 삽입 완료: {text[:50]}...")
        return f"서식을 유지하면서 텍스트를 삽입했습니다: {text[:50]}..."

    except Exception as e:
        logger.error(f"서식 유지 삽입 실패: {e}")
        return f"서식 유지 삽입 실패: {e}"


# ============================================================
# 고급 삽입 기능 (특정 위치에 삽입)
# ============================================================

@mcp.tool()
def insert_after_text(search_text: str, new_text: str, nth_occurrence: int = 1) -> str:
    """
    특정 텍스트를 찾아서 그 뒤에 새 텍스트를 삽입합니다.
    search_text: 찾을 텍스트
    new_text: 삽입할 텍스트
    nth_occurrence: 몇 번째 발견된 텍스트 뒤에 삽입할지 (1부터 시작, 기본값 1)
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        if not search_text:
            return "찾을 텍스트를 지정해주세요."

        # 문서 시작으로 이동
        hwp.HAction.Run("MoveDocBegin")

        # n번째 발견까지 반복 검색
        found_count = 0
        for i in range(nth_occurrence):
            hwp.HAction.GetDefault("RepeatFind", hwp.HParameterSet.HFindReplace.HSet)
            hwp.HParameterSet.HFindReplace.FindString = search_text

            result = hwp.HAction.Execute("RepeatFind", hwp.HParameterSet.HFindReplace.HSet)

            if not result:
                if i == 0:
                    return f"'{search_text}'를 찾을 수 없습니다."
                else:
                    return f"'{search_text}'를 {i}번만 찾았습니다. ({nth_occurrence}번째를 요청했으나 존재하지 않음)"

            found_count = i + 1

        # 찾은 텍스트의 끝으로 이동 (선택 영역의 오른쪽)
        hwp.HAction.Run("MoveSelRight")

        # 새 텍스트 삽입
        act = hwp.CreateAction("InsertText")
        pset = act.CreateSet()
        pset.SetItem("Text", new_text)
        act.Execute(pset)

        logger.info(f"'{search_text}' ({nth_occurrence}번째) 뒤에 '{new_text}' 삽입 완료")
        return f"'{search_text}' ({nth_occurrence}번째) 뒤에 '{new_text}'를 삽입했습니다."

    except Exception as e:
        logger.error(f"텍스트 뒤 삽입 실패: {e}")
        return f"텍스트 뒤 삽입 실패: {e}"


@mcp.tool()
def insert_before_text(search_text: str, new_text: str, nth_occurrence: int = 1) -> str:
    """
    특정 텍스트를 찾아서 그 앞에 새 텍스트를 삽입합니다.
    search_text: 찾을 텍스트
    new_text: 삽입할 텍스트
    nth_occurrence: 몇 번째 발견된 텍스트 앞에 삽입할지 (1부터 시작, 기본값 1)
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        if not search_text:
            return "찾을 텍스트를 지정해주세요."

        # 문서 시작으로 이동
        hwp.HAction.Run("MoveDocBegin")

        # n번째 발견까지 반복 검색
        found_count = 0
        for i in range(nth_occurrence):
            hwp.HAction.GetDefault("RepeatFind", hwp.HParameterSet.HFindReplace.HSet)
            hwp.HParameterSet.HFindReplace.FindString = search_text

            result = hwp.HAction.Execute("RepeatFind", hwp.HParameterSet.HFindReplace.HSet)

            if not result:
                if i == 0:
                    return f"'{search_text}'를 찾을 수 없습니다."
                else:
                    return f"'{search_text}'를 {i}번만 찾았습니다. ({nth_occurrence}번째를 요청했으나 존재하지 않음)"

            found_count = i + 1

        # 찾은 텍스트의 시작으로 이동 (선택 영역의 왼쪽)
        hwp.HAction.Run("MoveSelLeft")

        # 새 텍스트 삽입
        act = hwp.CreateAction("InsertText")
        pset = act.CreateSet()
        pset.SetItem("Text", new_text)
        act.Execute(pset)

        logger.info(f"'{search_text}' ({nth_occurrence}번째) 앞에 '{new_text}' 삽입 완료")
        return f"'{search_text}' ({nth_occurrence}번째) 앞에 '{new_text}'를 삽입했습니다."

    except Exception as e:
        logger.error(f"텍스트 앞 삽입 실패: {e}")
        return f"텍스트 앞 삽입 실패: {e}"


@mcp.tool()
def append_to_paragraph(paragraph_number: int, text: str) -> str:
    """
    특정 문단의 끝에 텍스트를 추가합니다.
    paragraph_number: 문단 번호 (0부터 시작)
    text: 추가할 텍스트
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        # 문단으로 이동
        hwp.HAction.Run("MoveDocBegin")
        for i in range(paragraph_number):
            hwp.HAction.Run("MoveParaDown")

        # 문단 끝으로 이동
        hwp.HAction.Run("MoveParaEnd")

        # 텍스트 삽입
        act = hwp.CreateAction("InsertText")
        pset = act.CreateSet()
        pset.SetItem("Text", text)
        act.Execute(pset)

        logger.info(f"{paragraph_number}번째 문단 끝에 텍스트 추가 완료")
        return f"{paragraph_number}번째 문단 끝에 '{text[:30]}...'를 추가했습니다."

    except Exception as e:
        logger.error(f"문단 끝 추가 실패: {e}")
        return f"문단 끝 추가 실패: {e}"


@mcp.tool()
def prepend_to_paragraph(paragraph_number: int, text: str) -> str:
    """
    특정 문단의 앞에 텍스트를 추가합니다.
    paragraph_number: 문단 번호 (0부터 시작)
    text: 추가할 텍스트
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        # 문단으로 이동
        hwp.HAction.Run("MoveDocBegin")
        for i in range(paragraph_number):
            hwp.HAction.Run("MoveParaDown")

        # 문단 시작으로 이동 (이미 시작 위치)
        # 텍스트 삽입
        act = hwp.CreateAction("InsertText")
        pset = act.CreateSet()
        pset.SetItem("Text", text)
        act.Execute(pset)

        logger.info(f"{paragraph_number}번째 문단 앞에 텍스트 추가 완료")
        return f"{paragraph_number}번째 문단 앞에 '{text[:30]}...'를 추가했습니다."

    except Exception as e:
        logger.error(f"문단 앞 추가 실패: {e}")
        return f"문단 앞 추가 실패: {e}"


@mcp.tool()
def insert_at_page_start(page_number: int, text: str) -> str:
    """
    특정 페이지의 시작 부분에 텍스트를 삽입합니다.
    page_number: 페이지 번호 (1부터 시작)
    text: 삽입할 텍스트
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        total_pages = hwp.PageCount
        if page_number < 1 or page_number > total_pages:
            return f"페이지 번호가 범위를 벗어났습니다. (1~{total_pages})"

        # 페이지로 이동
        hwp.HAction.GetDefault("Goto", hwp.HParameterSet.HGotoE.HSet)
        hwp.HParameterSet.HGotoE.PageNumber = page_number
        hwp.HAction.Execute("Goto", hwp.HParameterSet.HGotoE.HSet)

        # 페이지 시작으로 이동
        hwp.HAction.Run("MovePageBegin")

        # 텍스트 삽입
        act = hwp.CreateAction("InsertText")
        pset = act.CreateSet()
        pset.SetItem("Text", text)
        act.Execute(pset)

        logger.info(f"{page_number}페이지 시작에 텍스트 삽입 완료")
        return f"{page_number}페이지 시작에 '{text[:30]}...'를 삽입했습니다."

    except Exception as e:
        logger.error(f"페이지 시작 삽입 실패: {e}")
        return f"페이지 시작 삽입 실패: {e}"


@mcp.tool()
def insert_at_page_end(page_number: int, text: str) -> str:
    """
    특정 페이지의 끝 부분에 텍스트를 삽입합니다.
    page_number: 페이지 번호 (1부터 시작)
    text: 삽입할 텍스트
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        total_pages = hwp.PageCount
        if page_number < 1 or page_number > total_pages:
            return f"페이지 번호가 범위를 벗어났습니다. (1~{total_pages})"

        # 페이지로 이동
        hwp.HAction.GetDefault("Goto", hwp.HParameterSet.HGotoE.HSet)
        hwp.HParameterSet.HGotoE.PageNumber = page_number
        hwp.HAction.Execute("Goto", hwp.HParameterSet.HGotoE.HSet)

        # 페이지 끝으로 이동
        hwp.HAction.Run("MovePageEnd")

        # 텍스트 삽입
        act = hwp.CreateAction("InsertText")
        pset = act.CreateSet()
        pset.SetItem("Text", text)
        act.Execute(pset)

        logger.info(f"{page_number}페이지 끝에 텍스트 삽입 완료")
        return f"{page_number}페이지 끝에 '{text[:30]}...'를 삽입했습니다."

    except Exception as e:
        logger.error(f"페이지 끝 삽입 실패: {e}")
        return f"페이지 끝 삽입 실패: {e}"


# ============================================================
# 선택 기능
# ============================================================

@mcp.tool()
def select_paragraph_by_number(paragraph_number: int) -> str:
    """
    특정 문단을 선택합니다.
    paragraph_number: 선택할 문단 번호 (0부터 시작)
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        # 문단으로 이동
        hwp.HAction.Run("MoveDocBegin")
        for i in range(paragraph_number):
            hwp.HAction.Run("MoveParaDown")

        # 문단 선택
        hwp.HAction.Run("MoveSelParaDown")

        # 선택된 내용 확인
        selected_text = hwp.GetTextFile("TEXT", "")
        if selected_text is None:
            selected_text = ""

        logger.info(f"{paragraph_number}번째 문단 선택 완료")
        return f"{paragraph_number}번째 문단을 선택했습니다. ({len(selected_text)}자)"

    except Exception as e:
        logger.error(f"문단 선택 실패: {e}")
        return f"문단 선택 실패: {e}"


@mcp.tool()
def select_page_content(page_number: int) -> str:
    """
    특정 페이지의 모든 내용을 선택합니다.
    page_number: 선택할 페이지 번호 (1부터 시작)
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        total_pages = hwp.PageCount
        if page_number < 1 or page_number > total_pages:
            return f"페이지 번호가 범위를 벗어났습니다. (1~{total_pages})"

        # 페이지로 이동
        hwp.HAction.GetDefault("Goto", hwp.HParameterSet.HGotoE.HSet)
        hwp.HParameterSet.HGotoE.PageNumber = page_number
        hwp.HAction.Execute("Goto", hwp.HParameterSet.HGotoE.HSet)

        # 페이지 시작으로 이동
        hwp.HAction.Run("MovePageBegin")
        # 페이지 전체 선택
        hwp.HAction.Run("MoveSelPageDown")

        # 선택된 내용 확인
        selected_text = hwp.GetTextFile("TEXT", "")
        if selected_text is None:
            selected_text = ""

        logger.info(f"{page_number}페이지 선택 완료")
        return f"{page_number}페이지를 선택했습니다. ({len(selected_text)}자)"

    except Exception as e:
        logger.error(f"페이지 선택 실패: {e}")
        return f"페이지 선택 실패: {e}"


# ============================================================
# 성능 최적화 및 자동화 제어
# ============================================================

@mcp.tool()
def set_screen_updating(enabled: bool = True) -> str:
    """
    화면 업데이트를 켜거나 끕니다.
    대량 작업 시 False로 설정하면 성능이 크게 향상됩니다.
    작업 완료 후 반드시 True로 되돌려야 합니다.

    enabled: True=화면 업데이트 켜기, False=화면 업데이트 끄기
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        if enabled:
            hwp.SetScreenUpdate(1)  # 화면 업데이트 켜기
            logger.info("화면 업데이트 활성화")
            return "화면 업데이트를 활성화했습니다. (정상 속도)"
        else:
            hwp.SetScreenUpdate(0)  # 화면 업데이트 끄기
            logger.info("화면 업데이트 비활성화")
            return "화면 업데이트를 비활성화했습니다. (고속 모드)"

    except Exception as e:
        logger.error(f"화면 업데이트 설정 실패: {e}")
        return f"화면 업데이트 설정 실패: {e}"


@mcp.tool()
def set_automation_mode(enabled: bool = True) -> str:
    """
    자동화 모드를 켜거나 끕니다.
    enabled=True이면 모든 확인 대화상자가 자동으로 승인됩니다.

    enabled: True=자동화 모드 (대화상자 없음), False=일반 모드 (대화상자 표시)
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        if enabled:
            # 자동화 모드 활성화
            try:
                hwp.MessageBoxMode = 0  # 0=자동응답
            except:
                pass
            try:
                hwp.SetMessageBoxMode(0)
            except:
                pass
            logger.info("자동화 모드 활성화")
            return "자동화 모드를 활성화했습니다. (모든 확인창 자동 승인)"
        else:
            # 일반 모드로 전환
            try:
                hwp.MessageBoxMode = 1  # 1=대화상자표시
            except:
                pass
            try:
                hwp.SetMessageBoxMode(1)
            except:
                pass
            logger.info("일반 모드 활성화")
            return "일반 모드로 전환했습니다. (확인창 표시)"

    except Exception as e:
        logger.error(f"자동화 모드 설정 실패: {e}")
        return f"자동화 모드 설정 실패: {e}"


@mcp.tool()
def optimize_for_bulk_operations() -> str:
    """
    대량 작업을 위한 최적화 설정을 적용합니다.
    - 화면 업데이트 비활성화
    - 자동화 모드 활성화
    - 성능 최대화

    작업 완료 후 restore_normal_mode()를 호출하세요.
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        # 화면 업데이트 끄기
        try:
            hwp.SetScreenUpdate(0)
        except:
            pass

        # 자동화 모드 켜기
        try:
            hwp.MessageBoxMode = 0
        except:
            pass

        # 자동 저장 비활성화 (성능 향상)
        try:
            hwp.SetAutoSave(0)
        except:
            pass

        logger.info("대량 작업 최적화 모드 활성화")
        return "대량 작업 최적화 모드를 활성화했습니다. (최고 성능)\n작업 완료 후 restore_normal_mode()를 호출하세요."

    except Exception as e:
        logger.error(f"최적화 모드 설정 실패: {e}")
        return f"최적화 모드 설정 실패: {e}"


@mcp.tool()
def restore_normal_mode() -> str:
    """
    최적화 설정을 해제하고 일반 모드로 복원합니다.
    - 화면 업데이트 활성화
    - 자동 저장 활성화
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        # 화면 업데이트 켜기
        try:
            hwp.SetScreenUpdate(1)
        except:
            pass

        # 자동 저장 켜기
        try:
            hwp.SetAutoSave(1)
        except:
            pass

        # 화면 갱신
        try:
            hwp.Run("Repaginate")
        except:
            pass

        logger.info("일반 모드 복원 완료")
        return "일반 모드로 복원했습니다. (화면 업데이트 활성화)"

    except Exception as e:
        logger.error(f"일반 모드 복원 실패: {e}")
        return f"일반 모드 복원 실패: {e}"


@mcp.tool()
def replace_paragraph(paragraph_number: int, new_text: str) -> str:
    """
    특정 문단의 내용을 완전히 새 텍스트로 교체합니다.
    paragraph_number: 교체할 문단 번호 (0부터 시작)
    new_text: 새로운 텍스트
    """
    try:
        hwp_controller.check_initialization()
        hwp = hwp_controller.hwp

        # 문단으로 이동
        hwp.HAction.Run("MoveDocBegin")
        for i in range(paragraph_number):
            hwp.HAction.Run("MoveParaDown")

        # 문단 선택
        hwp.HAction.Run("MoveSelParaDown")

        # 기존 내용 확인
        old_text = hwp.GetTextFile("TEXT", "")
        if old_text is None:
            old_text = ""

        # 삭제
        hwp.HAction.Run("Delete")

        # 새 텍스트 삽입
        act = hwp.CreateAction("InsertText")
        pset = act.CreateSet()
        pset.SetItem("Text", new_text)
        act.Execute(pset)

        logger.info(f"{paragraph_number}번째 문단 교체 완료")
        return f"{paragraph_number}번째 문단을 교체했습니다.\n이전: {old_text[:50] if old_text else '(빈 문단)'}...\n새 내용: {new_text[:50]}..."

    except Exception as e:
        logger.error(f"문단 교체 실패: {e}")
        return f"문단 교체 실패: {e}"


def main():
    """메인 함수"""
    try:
        logger.info("Advanced HWP MCP Server 시작")
        
        mcp.run()
        
    except Exception as e:
        logger.error(f"서버 실행 중 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
