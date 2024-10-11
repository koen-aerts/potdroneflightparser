'''
SQLite DB Access - Developer: Koen Aerts
'''
import sqlite3

class Db():

    def dataFile(self):
        return self.dbFile

    def execute(self, expression, params=None):
        '''
        Run a SQL command and return results.
        '''
        con = sqlite3.connect(self.dbFile)
        cur = con.cursor()
        if (params):
            cur.execute(expression, params)
        else:
            cur.execute(expression)
        results = cur.fetchall()
        con.commit()
        con.close()
        return results

    def __init__(self, file, extdb=False):
        self.dbFile = file
        if extdb:
            return

        '''
        Create the DB and schema.
        '''
        self.execute("""
            CREATE TABLE IF NOT EXISTS models(
                modelref TEXT PRIMARY KEY
            )
        """)
        self.execute("""
            CREATE TABLE IF NOT EXISTS imports(
                importref TEXT PRIMARY KEY,
                modelref TEXT NOT NULL,
                dateref TEXT NOT NULL,
                importedon TEXT NOT NULL,
                FOREIGN KEY (modelref) REFERENCES models(modelref) ON DELETE CASCADE ON UPDATE NO ACTION
            )
        """)
        self.execute("""
            CREATE TABLE IF NOT EXISTS log_files(
                filename TEXT PRIMARY KEY,
                importref TEXT NOT NULL,
                bintype TEXT NOT NULL,
                FOREIGN KEY (importref) REFERENCES imports(importref) ON DELETE CASCADE ON UPDATE NO ACTION
            )
        """)
        self.execute("""
            CREATE TABLE IF NOT EXISTS flight_stats(
                importref TEXT NOT NULL,
                flight_number INTEGER NOT NULL,
                duration INTEGER NOT NULL,
                max_distance REAL NOT NULL,
                max_altitude REAL NOT NULL,
                max_h_speed REAL NOT NULL,
                max_v_speed REAL NOT NULL,
                traveled REAL NOT NULL,
                FOREIGN KEY (importref) REFERENCES imports(importref) ON DELETE CASCADE ON UPDATE NO ACTION
            )
        """)
        self.execute("CREATE INDEX IF NOT EXISTS flight_stats_index ON flight_stats(importref)")
