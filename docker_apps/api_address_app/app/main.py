from decouple import config

from db import mysql_connect
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, constr, ValidationError, field_validator
import district_service

app = FastAPI()
auth_token = config('TOKEN_API')


class Authorization(BaseModel):
    token: str

    @field_validator('token')
    @classmethod
    def force_x_positive(cls, token):
        if token != auth_token:
            raise HTTPException(
                status_code=401,
                detail="Invalid token. Please check your credentials."
            )


class Address(BaseModel):
    address_living: str
    address_living: constr(min_length=8, max_length=100)


@app.get("/get_district/", status_code=200)
async def get_district(token: str, address_living: str):
    msql = mysql_connect.MySQLClient()
    try:
        Authorization(token=token)
        Address(address_living=address_living)
        select_query = \
            f"""
            SELECT logistic_area
            FROM address_patients_logistic
            WHERE address_living='{address_living}'
            """
        logistic_area = msql.get_data_from_query(select_query)
        if len(logistic_area) > 0:
            msql.close_connect()
            return {'logistic_area': logistic_area[0][0]}
        else:
            logistic_area = district_service.main(msql, address_living)
            msql.close_connect()
            if logistic_area[0] is None:
                return {'logistic_area': 'Адрес не интерпретирован в район'}
            return {'logistic_area': logistic_area[0]}
    except ValidationError as e:
        msql.close_connect()
        raise HTTPException(
            status_code=401,
            detail=f"Invalid address. {repr(e.errors()[0]['type'])}"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
