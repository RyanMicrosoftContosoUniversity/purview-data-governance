use MASTER;

CREATE USER [governancePurviewRH] FROM EXTERNAL PROVIDER;


USE WWI;

ALTER ROLE db_datareader ADD MEMBER [governancePurviewRH];
ALTER ROLE db_datawriter ADD MEMBER [governancePurviewRH];
ALTER ROLE db_owner ADD MEMBER [governancePurviewRH];

GRANT VIEW DEFINITION TO [governancePurviewRH];
GRANT ALTER ANY DATABASE EVENT SESSION TO [governancePurviewRH];


GRANT VIEW DATABASE STATE TO [governancePurviewRH];
GRANT SELECT ON DATABASE::WWI TO [governancePurviewRH];

CREATE MASTER KEY ENCRYPTION BY PASSWORD = '$uper$strongPa$$word!';


SELECT name, type_desc FROM sys.database_principals WHERE name = 'governancePurviewRH';
