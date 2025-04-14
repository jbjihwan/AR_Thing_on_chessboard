import numpy as np
import cv2 as cv
import open3d as o3d
import copy

# The given video and calibration data
video_file = 'D:/CV/homework/AR_Thing_on_chessboard/data/chessboard.avi'
K = np.array(
 #=================1 image================================================
# [[3.13001947e+02, 0.00000000e+00, 1.04185593e+03],
#  [0.00000000e+00, 2.73523647e+02, 5.67008972e+02],
#  [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]]
 #=================44 images================================================
 #    [[760.60913613,   0,         966.35761847],
 # [  0,         708.76761067, 539.17018328],
 # [  0,           0,           1        ]]
 #=================76 images================================================
[[792.86298416,   0,         952.48662826],
 [  0,         734.3632487,  534.80188396],
 [  0,           0,           1        ]]
             ) # Derived from `calibrate_camera.py`
dist_coeff = np.array(
    # =================1 image================================================
    # [-0.03887438,  0.00777214,  0.00043639,  0.0014292,  -0.00086478]
    # =================44 images================================================
    # [-0.23078145,  0.17038474,  0.00320475,  0.00778075, -0.06751446]
    # =================76 images================================================
    [-0.24012391,  0.16793469, -0.00373626,  0.00596004, -0.06071182]
)
board_pattern = (10, 7)
board_cellsize = 0.025
board_criteria = cv.CALIB_CB_ADAPTIVE_THRESH + cv.CALIB_CB_NORMALIZE_IMAGE + cv.CALIB_CB_FAST_CHECK

mesh = o3d.io.read_triangle_mesh("D:/CV/homework/AR_Thing_on_chessboard/data/classic_ufo.glb", enable_post_processing=True)
mesh.compute_vertex_normals()
mesh.scale(0.2, center=mesh.get_center())

R = mesh.get_rotation_matrix_from_xyz((np.pi / 2, 0, 0))
mesh.rotate(R, center=mesh.get_center())

center_3d = np.array([5.5, 3.5, -0.2]) * board_cellsize
mesh.translate(center_3d)

rotation_angle = 0.0

vertices = np.asarray(mesh.vertices)
edges = np.asarray(mesh.triangles)

# Open a video
video = cv.VideoCapture(video_file)
assert video.isOpened(), 'Cannot read the given input, ' + video_file

# Prepare a 3D box for simple AR
box_lower = board_cellsize * np.array([[4, 2,  0], [5, 2,  0], [5, 4,  0], [4, 4,  0]])
box_upper = board_cellsize * np.array([[5, 3, -1], [6, 3, -1], [6, 5, -1], [5, 5, -1]])


# Prepare 3D points on a chessboard
obj_points = board_cellsize * np.array([[c, r, 0] for r in range(board_pattern[1]) for c in range(board_pattern[0])])

# Draw sphere
def draw_sphere(img, center_3d, radius_world, rvec, tvec, K, dist_coeff, color=(0, 0, 255)):
    # 중심 투영
    center_2d, _ = cv.projectPoints(np.array([center_3d]), rvec, tvec, K, dist_coeff)
    center_2d = tuple(np.int32(center_2d[0].flatten()))

    # 투영된 반지름 계산
    edge_3d = center_3d + np.array([radius_world, 0, 0])  # x축으로 이동한 점
    edge_2d, _ = cv.projectPoints(np.array([edge_3d]), rvec, tvec, K, dist_coeff)
    edge_2d = edge_2d[0].flatten()
    projected_radius = int(np.linalg.norm(center_2d - edge_2d))

    # 그라데이션 효과로 구 그리기 (밝은 → 어두운 색)
    steps = 20
    for i in range(steps, 0, -1):
        alpha = i / steps
        r = int(projected_radius * alpha)
        shade = tuple(int(c * (0.5 + 0.5 * alpha)) for c in color)  # 빛 반사 효과
        cv.circle(img, center_2d, r, shade, -1)

# Draw cube
def draw_cube(img, center, size, rvec, tvec, K, dist_coeff):
    s = size / 2

    cube_3d = np.array([
        [center[0] - s, center[1] - s, center[2] - s],
        [center[0] + s, center[1] - s, center[2] - s],
        [center[0] + s, center[1] + s, center[2] - s],
        [center[0] - s, center[1] + s, center[2] - s],
        [center[0] - s, center[1] - s, center[2] + s],
        [center[0] + s, center[1] - s, center[2] + s],
        [center[0] + s, center[1] + s, center[2] + s],
        [center[0] - s, center[1] + s, center[2] + s]
    ])

    projected, _ = cv.projectPoints(cube_3d, rvec, tvec, K, dist_coeff)
    projected = np.int32(projected).reshape(-1, 2)

    # 하단 사각형
    cv.polylines(img, [projected[0:4]], True, (255, 255, 0), 2)
    # 상단 사각형
    cv.polylines(img, [projected[4:8]], True, (0, 255, 255), 2)
    # 수직 연결선
    for i in range(4):
        cv.line(img, projected[i], projected[i + 4], (0, 255, 0), 2)

def draw_saturn(img, center_3d, rvec, tvec, K, dist_coeff):
    # 중심 투영
    center_2d, _ = cv.projectPoints(np.array([center_3d]), rvec, tvec, K, dist_coeff)
    center_2d = tuple(np.int32(center_2d[0].flatten()))

    # 고리 외곽과 내곽 계산 (타원)
    outer_radius = 140
    inner_radius = 70
    cv.ellipse(img, center_2d, (outer_radius, int(outer_radius * 1)), 0, 0, 360, (180, 180, 180), -1)
    cv.ellipse(img, center_2d, (inner_radius, int(inner_radius * 1)), 0, 0, 360, (0, 0, 0), -1)
    cv.circle(img, center_2d, 20, (200, 200, 255), -1)  # 중심 행성

def draw_face(img, center_3d, rvec, tvec, K, dist_coeff):
    center_2d, _ = cv.projectPoints(np.array([center_3d]), rvec, tvec, K, dist_coeff)
    cx, cy = tuple(np.int32(center_2d[0].flatten()))
    # 얼굴 원
    cv.circle(img, (cx, cy), 30, (255, 255, 200), -1)
    # 눈
    cv.circle(img, (cx - 10, cy - 10), 5, (0, 0, 0), -1)
    cv.circle(img, (cx + 10, cy - 10), 5, (0, 0, 0), -1)
    # 입
    cv.ellipse(img, (cx, cy + 10), (10, 5), 0, 0, 180, (0, 0, 0), 2)

def draw_3d_model(img, rvec, tvec, K, dist_coeff):
    projected, _ = cv.projectPoints(vertices, rvec, tvec, K, dist_coeff)
    projected = projected.reshape(-1, 2).astype(np.int32)
    for tri in edges:
        pts = projected[tri]
        cv.polylines(img, [pts], isClosed=True, color=(255, 100, 100), thickness=1)

# Run pose estimation
while True:
    # Read an image from the video
    valid, img = video.read()
    if not valid:
        break

    # Estimate the camera pose
    success, img_points = cv.findChessboardCorners(img, board_pattern, board_criteria)
    if success:
        ret, rvec, tvec = cv.solvePnP(obj_points, img_points, K, dist_coeff)

        # Draw the box on the image
        # line_lower, _ = cv.projectPoints(box_lower, rvec, tvec, K, dist_coeff)
        # line_upper, _ = cv.projectPoints(box_upper, rvec, tvec, K, dist_coeff)
        # cv.polylines(img, [np.int32(line_lower)], True, (255, 0, 0), 2)
        # cv.polylines(img, [np.int32(line_upper)], True, (0, 0, 255), 2)
        # for b, t in zip(line_lower, line_upper):
        #     cv.line(img, np.int32(b.flatten()), np.int32(t.flatten()), (0, 255, 0), 2)

        # === 구체 제거 후 UFO나 큐브 등으로 대체 ===
        # cube_center = np.array([5.5, 3.5, -1.0]) * board_cellsize
        # cube_size = 0.06  # 6cm 큐브
        # draw_cube(img, cube_center, cube_size, rvec, tvec, K, dist_coeff)

        # 회전 각도 증가 (매 프레임마다 조금씩)
        rotation_angle += np.pi / 180  # 1도씩 증가

        # 이전 회전 제거를 위해 원본부터 다시 복사
        mesh_copy = copy.deepcopy(mesh)

        # 회전 행렬 생성 (Y축 기준 회전)
        R_anim = mesh_copy.get_rotation_matrix_from_xyz((0, rotation_angle, 0))
        mesh_copy.rotate(R_anim, center=mesh_copy.get_center())

        # 정점 추출해서 AR 투영
        vertices = np.asarray(mesh_copy.vertices)
        edges = np.asarray(mesh_copy.triangles)

        # === 원하는 도형 선택해서 그리기 ===
        center_3d = np.array([5.5, 3.5, -1.0]) * board_cellsize
        # draw_saturn(img, center_3d, rvec, tvec, K, dist_coeff)  # 🪐 토성형 고리
        # draw_face(img, center_3d + [0.05, 0, 0], rvec, tvec, K, dist_coeff)  # 🤖 얼굴
        # draw_cube(img, center_3d + [0.1, 0, 0], 0.05, rvec, tvec, K, dist_coeff)  # 📦 큐브
        draw_3d_model(img, rvec, tvec, K, dist_coeff)

        # Print the camera position
        R, _ = cv.Rodrigues(rvec) # Alternative) `scipy.spatial.transform.Rotation`
        p = (-R.T @ tvec).flatten()
        info = f'XYZ: [{p[0]:.3f} {p[1]:.3f} {p[2]:.3f}]'
        cv.putText(img, info, (10, 25), cv.FONT_HERSHEY_DUPLEX, 0.6, (0, 255, 0))


    # Show the image and process the key event
    cv.imshow('Pose Estimation (Chessboard)', img)
    key = cv.waitKey(10)
    if key == ord(' '):
        key = cv.waitKey()
    if key == 27: # ESC
        break

video.release()
cv.destroyAllWindows()

