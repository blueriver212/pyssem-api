FROM python:3.9

EXPOSE 5000

ENV PYTHONDONTWRITEBYTECODE=1

ENV PYTHONUNBUFFERED=1

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

RUN pip install --upgrade pip setuptools && \
    pip uninstall pyssem && \
    pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ pyssem==0.1.dev215
WORKDIR /app
COPY . /app
COPY ./x0_launch_repeatlaunch_2018to2022_megaconstellationLaunches_Constellations.csv pyssem/utils/launch/data/x0_launch_repeatlaunch_2018to2022_megaconstellationLaunches_Constellations.csv

RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run_model:app"]
