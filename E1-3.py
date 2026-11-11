"""
MAC 필터 판정 콘솔 애플리케이션
- 모드 1: 사용자 입력(3x3) 필터 A/B + 패턴 판정
- 모드 2: data.json 일괄 분석 + 성능 분석 + 리포트
외부 라이브러리 금지(표준 라이브러리만 사용)
"""
import json
import time

EPSILON = 1e-9          # 점수 동점 판정 허용오차
REPEAT = 10             # 성능 측정 반복 횟수


# ---------------------------------------------------------------------------
# 데이터 구조: n x n 패턴/필터를 담는 Matrix
# ---------------------------------------------------------------------------
class Matrix:
    def __init__(self, data):
        self.data = data
        self.n = len(data)

    def get(self, r, c):
        return self.data[r][c]

    def set(self, r, c, value):
        self.data[r][c] = value

    @property
    def size(self):
        return self.n


# ---------------------------------------------------------------------------
# 라벨 정규화: 내부 표준 라벨은 "Cross", "X" 두 가지만 사용
# ---------------------------------------------------------------------------
def normalize_label(raw):
    """expected 값('+','x') 또는 filter 키('cross','x')를 표준 라벨로 변환."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in ("+", "cross", "십자가"):
        return "Cross"
    if s in ("x", "엑스"):
        return "X"
    return None  # 알 수 없는 라벨


# ---------------------------------------------------------------------------
# MAC 연산: 위치별 곱의 총합 (반복문 직접 구현)
# ---------------------------------------------------------------------------
def mac(pattern, filt):
    """pattern과 filt를 위치별로 곱해 모두 더한 점수(float) 반환."""
    if pattern.size != filt.size:
        raise ValueError(
            f"크기 불일치: pattern={pattern.size}, filter={filt.size}")
    n = pattern.size
    score = 0.0
    for r in range(n):
        for c in range(n):
            score += pattern.get(r, c) * filt.get(r, c)
    return score


# ---------------------------------------------------------------------------
# 판정: epsilon 기반 비교로 Cross/X/UNDECIDED 결정
# ---------------------------------------------------------------------------
def decide(score_cross, score_x):
    """두 점수를 비교해 표준 라벨 또는 UNDECIDED 반환."""
    if abs(score_cross - score_x) < EPSILON:
        return "UNDECIDED"
    return "Cross" if score_cross > score_x else "X"


# ---------------------------------------------------------------------------
# 성능 측정: MAC 연산을 REPEAT회 반복하여 평균 시간(ms) 산출
# ---------------------------------------------------------------------------
def measure_mac(pattern, filt, repeat=REPEAT):
    """연산 함수 구간만 측정(I/O 제외). 평균 ms 반환."""
    start = time.perf_counter()
    for _ in range(repeat):
        mac(pattern, filt)
    elapsed = time.perf_counter() - start
    return (elapsed / repeat) * 1000.0  # ms
    # ---------------------------------------------------------------------------
# 모드 1: 사용자 입력(3x3) - 행/열 개수 및 숫자 파싱 검증 + 재입력 유도
# ---------------------------------------------------------------------------
def read_matrix_from_console(name, n=3):
    """n개의 줄을 공백 구분으로 입력받아 Matrix 생성. 오류 시 재입력."""
    print(f"\n[{name}] {n}x{n} 값을 한 줄에 {n}개씩, 공백으로 구분해 입력하세요.")
    while True:
        rows = []
        ok = True
        for i in range(n):
            line = input(f"  {name} {i + 1}행: ").strip()
            parts = line.split()
            # 열 개수 검증
            if len(parts) != n:
                print(f"입력 형식 오류: 각 줄에 {n}개의 숫자를 공백으로 구분해 입력하세요.")
                ok = False
                break
            # 숫자 파싱 검증
            try:
                nums = [float(p) for p in parts]
            except ValueError:
                print("입력 형식 오류: 숫자만 입력할 수 있습니다. 다시 입력하세요.")
                ok = False
                break
            rows.append(nums)
        if ok and len(rows) == n:
            return Matrix(rows)
        print("--- 처음부터 다시 입력합니다 ---")


def run_mode1():
    print("\n===== 모드 1: 사용자 입력(3x3) =====")
    filter_a = read_matrix_from_console("필터 A(Cross)")
    filter_b = read_matrix_from_console("필터 B(X)")
    print("필터 A, B 저장 완료.")
    pattern = read_matrix_from_console("패턴")
    print("패턴 저장 완료.")

    # MAC 연산
    score_a = mac(pattern, filter_a)
    score_b = mac(pattern, filter_b)

    # 판정 (A=Cross, B=X 로 매핑)
    verdict = decide(score_a, score_b)
    if verdict == "Cross":
        result_text = "A(Cross)"
    elif verdict == "X":
        result_text = "B(X)"
    else:
        result_text = "판정 불가(UNDECIDED)"

    # 성능 측정 (3x3)
    t_a = measure_mac(pattern, filter_a)

    print("\n----- 결과 -----")
    print(f"필터 A(Cross) 점수 : {score_a}")
    print(f"필터 B(X)     점수 : {score_b}")
    print(f"판정 결과          : {result_text}")
    print(f"연산 시간(3x3)     : {t_a:.6f} ms (10회 평균)")


# ---------------------------------------------------------------------------
# 모드 2: data.json 로드 + 스키마 검증 + 일괄 판정
# ---------------------------------------------------------------------------
def load_json(path="data.json"):
    """JSON 로드. 실패 시 None 반환(프로그램 중단 방지)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"오류: {path} 파일을 찾을 수 없습니다.")
    except json.JSONDecodeError as e:
        print(f"오류: {path} JSON 파싱 실패 - {e}")
    return None


def extract_n_from_key(key):
    """'size_5_0' 같은 키에서 N(=5)을 정수로 추출. 실패 시 None."""
    parts = key.split("_")
    for p in parts:
        if p.isdigit():
            return int(p)
    return None


def build_filter_matrix(raw_filter):
    """
    필터 데이터는 {'cross': [[...]], 'x': [[...]]} 형태를 기대.
    표준 라벨(Cross/X) -> Matrix 로 매핑한 dict 반환.
    """
    result = {}
    for raw_label, grid in raw_filter.items():
        label = normalize_label(raw_label)
        if label is not None:
            result[label] = Matrix(grid)
    return result


def run_mode2(path="data.json"):
    print("\n===== 모드 2: data.json 분석 =====")
    data = load_json(path)
    if data is None:
        return

    filters = data.get("filters", {})
    patterns = data.get("patterns", {})

    results = []   # (case_id, verdict, expected, status, reason)

    for case_id, item in patterns.items():
        # --- 스키마 검증: input / expected 존재 여부 ---
        if "input" not in item or "expected" not in item:
            results.append((case_id, "-", "-", "FAIL",
                            "스키마 오류: input/expected 누락"))
            continue

        # --- N 추출 및 해당 필터 선택 ---
        n = extract_n_from_key(case_id)
        if n is None:
            results.append((case_id, "-", "-", "FAIL",
                            "키에서 N 추출 실패"))
            continue

        filt_key = f"size_{n}"
        if filt_key not in filters:
            results.append((case_id, "-", "-", "FAIL",
                            f"필터 {filt_key} 없음"))
            continue

        filt_map = build_filter_matrix(filters[filt_key])
        if "Cross" not in filt_map or "X" not in filt_map:
            results.append((case_id, "-", "-", "FAIL",
                            "필터 라벨(Cross/X) 정규화 실패"))
            continue

        pattern = Matrix(item["input"])
        expected = normalize_label(item["expected"])
        if expected is None:
            results.append((case_id, "-", str(item["expected"]), "FAIL",
                            "expected 라벨 정규화 실패"))
            continue

        # --- 크기 일치 검증 + MAC 연산 (케이스 단위 예외 처리) ---
        try:
            score_cross = mac(pattern, filt_map["Cross"])
            score_x = mac(pattern, filt_map["X"])
        except ValueError as e:
            results.append((case_id, "-", expected, "FAIL", str(e)))
            continue

        verdict = decide(score_cross, score_x)
        status = "PASS" if verdict == expected else "FAIL"
        reason = "" if status == "PASS" else f"판정({verdict}) != expected({expected})"

        print(f"[{case_id}] Cross={score_cross:.4f}  X={score_x:.4f}  "
              f"판정={verdict}  expected={expected}  -> {status}")
        results.append((case_id, verdict, expected, status, reason))

    # --- 성능 분석표 ---
    print_performance_table(filters)

    # --- 결과 요약 ---
    print_summary(results)
    # ---------------------------------------------------------------------------
# 성능 분석표: 크기별 평균 시간(ms)과 연산 횟수(N^2) 출력
# ---------------------------------------------------------------------------
def print_performance_table(filters):
    print("\n----- 성능 분석표 (MAC 연산, 10회 평균) -----")
    print(f"{'크기(N×N)':<12}{'평균 시간(ms)':<16}{'연산 횟수(N²)':<12}")
    print("-" * 40)

    # 측정 대상 크기: 3, 5, 13, 25 (필터가 있으면 그 필터로, 없으면 임시 생성)
    for n in (3, 5, 13, 25):
        filt_key = f"size_{n}"
        if filt_key in filters:
            fmap = build_filter_matrix(filters[filt_key])
            filt = fmap.get("Cross")
        else:
            filt = None

        # 필터가 없으면 1로 채운 n×n 임시 행렬로 측정
        if filt is None:
            filt = Matrix([[1.0] * n for _ in range(n)])
        pattern = Matrix([[1.0] * n for _ in range(n)])

        avg_ms = measure_mac(pattern, filt)
        print(f"{f'{n}×{n}':<12}{avg_ms:<16.6f}{n * n:<12}")
    print("-" * 40)


# ---------------------------------------------------------------------------
# 결과 요약: 전체/통과/실패 수 + 실패 케이스 목록
# ---------------------------------------------------------------------------
def print_summary(results):
    total = len(results)
    passed = sum(1 for r in results if r[3] == "PASS")
    failed = total - passed

    print("\n===== 결과 요약 =====")
    print(f"전체 테스트 : {total}")
    print(f"통과(PASS) : {passed}")
    print(f"실패(FAIL) : {failed}")

    if failed > 0:
        print("\n-- 실패 케이스 --")
        for case_id, verdict, expected, status, reason in results:
            if status == "FAIL":
                print(f"  [{case_id}] 사유: {reason}")
    else:
        print("실패 케이스 없음. (라벨 정규화 + epsilon 정책이 올바르게 동작)")


# ---------------------------------------------------------------------------
# main 진입점: 모드 선택 흐름
# ---------------------------------------------------------------------------
def main():
    print("=" * 45)
    print(" MAC 필터 판정 애플리케이션")
    print("=" * 45)
    print("1) 사용자 입력(3×3)")
    print("2) data.json 분석")

    while True:
        choice = input("모드를 선택하세요 (1/2): ").strip()
        if choice == "1":
            run_mode1()
            break
        elif choice == "2":
            run_mode2()
            break
        else:
            print("잘못된 입력입니다. 1 또는 2를 입력하세요.")


if __name__ == "__main__":
    main()