from datetime import date, datetime, time, timedelta

import pandas as pd
import pytz

from sample_code.dao.audit import AuditDAO
from sample_code.dao.reporting import ReportDAO
from sample_code.dao.usage import UsageDAO
from sample_code.settings import (
    AUDIT_DATABASE,
    AUDIT_PASSWORD,
    AUDIT_REPLICASET,
    AUDIT_SERVER,
    AUDIT_USERNAME,
    DATABASE,
    PASSWORD,
    REPLICASET_A,
    REPLICASET_B,
    REPLICASET_C,
    REPORTING_AULDATALEAK_TABLENAME,
    SERVER_A,
    SERVER_B,
    SERVER_C,
    USERNAME,
)


class Main:
    def __init__(self) -> None:
        self.reportingClient = ReportDAO()

        self.auditClient = AuditDAO(
            mongoServers=AUDIT_SERVER,
            mongoReplicaset=AUDIT_REPLICASET,
            username=AUDIT_USERNAME,
            password=AUDIT_PASSWORD,
            database=AUDIT_DATABASE,
        )

        self.usageClient_A = UsageDAO(
            mongoServers=SERVER_A,
            mongoReplicaset=REPLICASET_A,
            username=USERNAME,
            password=PASSWORD,
            database=DATABASE,
        )

        self.usageClient_B = UsageDAO(
            mongoServers=SERVER_B,
            mongoReplicaset=REPLICASET_B,
            username=USERNAME,
            password=PASSWORD,
            database=DATABASE,
        )

        self.usageClient_C = UsageDAO(
            mongoServers=SERVER_C,
            mongoReplicaset=REPLICASET_C,
            username=USERNAME,
            password=PASSWORD,
            database=DATABASE,
        )

    def get_auldata_subscribers(self, auditRangeStart, auditRangeEnd):
        res = self.auditClient.get_subscribers(auditRangeStart, auditRangeEnd)
        return pd.DataFrame(list(res))

    def compare(self, auldataSubs):
        subListA = []
        subListB = []
        subListC = []

        for _, row in auldataSubs.iterrows():
            remainder = int(row["ban"]) % 3
            if remainder == 0:
                subListA.append(row)
            elif remainder == 1:
                subListB.append(row)
            elif remainder == 2:
                subListC.append(row)

        self.run_compare_on_node("A", subListA)
        self.run_compare_on_node("B", subListB)
        self.run_compare_on_node("C", subListC)

    def run_compare_on_node(self, node: str, subList: list):
        to_date = lambda d: datetime.strptime(d, "%Y-%m-%dT%H:%M:%SZ").astimezone(
            pytz.timezone("US/Eastern")
        )

        if len(subList) > 0:
            auditDate = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            usageClient = getattr(self, f"usageClient_{node}", None)

            if not usageClient:
                raise Exception("Wrong node!")

            usageResult = pd.DataFrame(
                columns=[
                    "extSubId",
                    "MDN",
                    "BAN",
                    "start",
                    "end",
                    "bytesIn",
                    "bytesOut",
                ]
            )

            for subscriber in subList:
                effectiveDate = to_date(subscriber["effectiveDate"])
                expiryDate = to_date(subscriber["expiryDate"])

                res = usageClient.get_subscriber_usage(
                    subscriber["subscriberId"], effectiveDate, expiryDate
                )
                usageResult = pd.concat([usageResult, pd.DataFrame(res)], axis=0)

            if len(usageResult) > 0:
                data = [
                    [
                        row["extSubId"],
                        row["MDN"],
                        row["BAN"],
                        row["start"],
                        row["end"],
                        int(row["bytesIn"]) + int(row["bytesOut"]),
                        auditDate,
                    ]
                    for _, row in usageResult.iterrows()
                ]

                self.reportingClient.insert_reporting_data(data)
                print(
                    f"{usageResult.size} rows written to {REPORTING_AULDATALEAK_TABLENAME}"
                )


if __name__ == "__main__":
    mainClient = Main()
    mainClient.reportingClient.create_reporting_table()

    auditDate = date.today() - timedelta(days=1)
    auditRangeStart = datetime.combine(auditDate, time(0, 0, 0))
    auditRangeEnd = datetime.combine(auditDate, time(23, 59, 59))

    auldataSubs = mainClient.get_auldata_subscribers(auditRangeStart, auditRangeEnd)
    mainClient.compare(auldataSubs)

    mainClient.reportingClient.clean_reporting_data()
