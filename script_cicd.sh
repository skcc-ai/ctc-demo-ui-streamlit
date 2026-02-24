#!/bin/bash

# 변수 설정
ACR_NAME="ctcdemo1770171004.azurecr.io"
IMAGE_NAME="demo-ui"
IMAGE_TAG="latest"
DEPLOYMENT_NAME="demo-ui-app"
NAMESPACE="demo-ui"

# ACR 로그인
az acr login --name $ACR_NAME

# 이미지 빌드 및 푸시 (완료될 때까지 대기)
az acr build \
  --registry $ACR_NAME \
  --image $IMAGE_NAME:$IMAGE_TAG \
  .

# 빌드 성공 여부 확인
if [ $? -ne 0 ]; then
  echo "빌드 실패. 롤아웃 중단"
  exit 1
fi

echo "빌드 완료: $ACR_NAME/$IMAGE_NAME:$IMAGE_TAG"

# 롤아웃 재시작
kubectl rollout restart deployment/$DEPLOYMENT_NAME -n $NAMESPACE

# 롤아웃 완료 대기
kubectl rollout status deployment/$DEPLOYMENT_NAME -n $NAMESPACE

echo "배포 완료"

az acr run --registry $ACR_NAME --cmd "acr purge --filter '<repo>:.*' --untagged --ago 7d" /dev/null

echo "ACR에 태그 없는 이미지 삭제"