FROM python:3.11-slim AS whisper-builder

ARG WHISPER_CPP_COMMIT=371b5a7561823ab2bb32142d2751e35e7534727b
ARG WHISPER_MODEL_URL=https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin
ARG WHISPER_MODEL_SHA256=422f1ae452ade6f30a004d7e5c6a43195e4433bc370bf23fac9cc591f01a8898

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/ggml-org/whisper.cpp.git /src/whisper.cpp \
    && git -C /src/whisper.cpp checkout "$WHISPER_CPP_COMMIT" \
    && cmake -S /src/whisper.cpp -B /src/whisper.cpp/build \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=OFF \
        -DGGML_NATIVE=OFF \
        -DWHISPER_BUILD_TESTS=OFF \
        -DWHISPER_BUILD_EXAMPLES=ON \
    && cmake --build /src/whisper.cpp/build --config Release \
        --target whisper-cli -j2

RUN mkdir -p /models \
    && curl -L --fail --retry 5 --retry-all-errors \
        --output /models/ggml-base-q5_1.bin "$WHISPER_MODEL_URL" \
    && echo "$WHISPER_MODEL_SHA256  /models/ggml-base-q5_1.bin" | sha256sum -c -

FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p /app/models /app/asr-models

COPY --from=whisper-builder /src/whisper.cpp/build/bin/whisper-cli /usr/local/bin/whisper-cli
COPY --from=whisper-builder /models/ggml-base-q5_1.bin /app/asr-models/ggml-base-q5_1.bin

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 9999

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9999"]
