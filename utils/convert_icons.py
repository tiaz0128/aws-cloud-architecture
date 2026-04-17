import re
import json
from pathlib import Path
from typing import Optional

ICON_PREFIX = "azr"

# 파일명에서 제거할 문자열 리스트 예시 (정규표현식 지원)
REMOVE_STRINGS = [
    r".+-icon-service-",  #
]

DEFAULT_WIDTH = 48
DEFAULT_HEIGHT = 48


def normalize_icon_name(filename: str, remove_strings: list[str] = None) -> str:
    """
    파일명을 정규화합니다.

    Args:
        filename: 원본 파일명 (확장자 제외)
        remove_strings: 파일명에서 제거할 문자열 리스트 (정규표현식 지원)
                       예: ["azure-", r"\d+", "icon$"]

    Returns:
        정규화된 파일명 (소문자와 언더바만)
    """
    if remove_strings is None:
        remove_strings = []

    # 지정된 문자열들 제거 (정규표현식 지원)
    for remove_str in remove_strings:
        try:
            # 정규표현식으로 시도
            filename = re.sub(remove_str, "", filename)
        except re.error:
            # 정규표현식이 아닌 일반 문자열로 처리
            filename = filename.replace(remove_str, "")

    # 특수문자를 언더바로 변환하고 소문자로 변환
    filename = re.sub(r"[^a-zA-Z0-9_]", "_", filename)
    filename = filename.lower()

    # 연속된 언더바를 하나로 줄이기
    filename = re.sub(r"_+", "_", filename)

    # 앞뒤 언더바 제거
    filename = filename.strip("_")

    return filename


def extract_svg_body(svg_content: str) -> str:
    """
    SVG 파일 내용에서 body 부분만 추출합니다.

    Args:
        svg_content: SVG 파일의 전체 내용

    Returns:
        추출된 body 문자열
    """
    # XML 선언 제거
    svg_content = re.sub(r"<\?xml[^>]*\?>", "", svg_content)

    # 주석 제거
    svg_content = re.sub(r"<!--.*?-->", "", svg_content, flags=re.DOTALL)

    # svg 태그 찾기 및 내용 추출
    svg_match = re.search(r"<svg[^>]*>(.*)</svg>", svg_content, re.DOTALL)

    if not svg_match:
        raise ValueError("유효한 SVG 태그를 찾을 수 없습니다.")

    inner_content = svg_match.group(1)

    # 불필요한 공백 및 줄바꿈 제거
    inner_content = re.sub(r"\s+", " ", inner_content)
    inner_content = inner_content.strip()

    return inner_content


def extract_svg_dimensions(svg_content: str) -> tuple[int, int]:
    """
    SVG의 viewBox에서 width와 height를 추출합니다.

    Args:
        svg_content: SVG 파일의 전체 내용

    Returns:
        (width, height) 튜플
    """
    # viewBox 속성에서 크기 추출
    viewbox_match = re.search(r'viewBox=["\']([^"\']+)["\']', svg_content)

    if viewbox_match:
        viewbox_values = viewbox_match.group(1).split()
        if len(viewbox_values) >= 4:
            width = int(float(viewbox_values[2]))
            height = int(float(viewbox_values[3]))
            return width, height

    # viewBox가 없으면 width, height 속성에서 추출
    width_match = re.search(r'width=["\'](\d+)["\']', svg_content)
    height_match = re.search(r'height=["\'](\d+)["\']', svg_content)

    if width_match and height_match:
        return int(width_match.group(1)), int(height_match.group(1))

    # 기본값 반환
    return DEFAULT_WIDTH, DEFAULT_HEIGHT


def svg_to_json_body(
    svg_file_path: str,
    icon_name: str,
    output_width: int = DEFAULT_WIDTH,
    output_height: int = DEFAULT_HEIGHT,
) -> dict:
    """
    SVG 파일을 JSON 형식의 body로 변환합니다.

    Args:
        svg_file_path: SVG 파일 경로
        icon_name: 아이콘 이름 (키로 사용)
        output_width: 출력 width (기본값)
        output_height: 출력 height (기본값)

    Returns:
        JSON 형식의 딕셔너리
    """
    # SVG 파일 읽기
    svg_path = Path(svg_file_path)

    if not svg_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {svg_file_path}")

    with open(svg_path, "r", encoding="utf-8") as f:
        svg_content = f.read()

    # body 추출
    body = extract_svg_body(svg_content)

    # JSON 형식으로 변환
    result = {icon_name: {"width": output_width, "height": output_height, "body": body}}

    return result


def process_multiple_svgs(
    svg_files: list[tuple[str, str]],
    output_file: Optional[str] = None,
    output_width: int = DEFAULT_WIDTH,
    output_height: int = DEFAULT_HEIGHT,
    remove_strings: list[str] = None,
) -> dict:
    """
    여러 SVG 파일을 한 번에 처리합니다.

    Args:
        svg_files: [(파일경로, 아이콘명), ...] 형식의 리스트
        output_file: 출력 파일 경로 (None이면 출력하지 않음)
        output_width: 출력 width
        output_height: 출력 height
        remove_strings: 파일명에서 제거할 문자열 리스트 (정규표현식 지원)
                       예: ["azure-", r"\d+", "icon$"]

    Returns:
        icons를 포함하는 딕셔너리
    """
    if remove_strings is None:
        remove_strings = []

    all_icons = {}

    for svg_path, icon_name in svg_files:
        try:
            # 파일명 정규화
            normalized_name = normalize_icon_name(icon_name, remove_strings)

            icon_data = svg_to_json_body(
                svg_path, normalized_name, output_width, output_height
            )
            all_icons.update(icon_data)
            print(f"✓ {icon_name} -> {normalized_name} 변환 완료")
        except Exception as e:
            print(f"✗ {icon_name} 변환 실패: {e}")

    # 최종 결과 구조 생성
    result = {"prefix": ICON_PREFIX, "icons": all_icons}

    # 파일로 출력
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        print(f"\n결과가 {output_file}에 저장되었습니다.")

    return result


# icons/{prefix} 폴더 내에 있는 모든 SVG 파일을 아이콘명으로 변환
if __name__ == "__main__":
    svg_list = [(str(p), p.stem) for p in Path(f"icons/{ICON_PREFIX}").glob("*.svg")]
    process_multiple_svgs(
        svg_list,
        output_file=f"{ICON_PREFIX}.json",
        remove_strings=REMOVE_STRINGS,
    )
