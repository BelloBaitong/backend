import { MigrationInterface, QueryRunner } from "typeorm";

export class AutoMigration1772592538143 implements MigrationInterface {
    name = 'AutoMigration1772592538143'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`CREATE TABLE "user_profile" ("id" SERIAL NOT NULL, "userId" integer NOT NULL, "studyYear" integer, "interests" text array NOT NULL DEFAULT ARRAY[]::text[], "careerGoals" text array NOT NULL DEFAULT ARRAY[]::text[], "createdAt" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "updatedAt" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), CONSTRAINT "UQ_51cb79b5555effaf7d69ba1cff9" UNIQUE ("userId"), CONSTRAINT "REL_51cb79b5555effaf7d69ba1cff" UNIQUE ("userId"), CONSTRAINT "PK_f44d0cd18cfd80b0fed7806c3b7" PRIMARY KEY ("id"))`);
        await queryRunner.query(`ALTER TABLE "user_profile" ADD CONSTRAINT "FK_51cb79b5555effaf7d69ba1cff9" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE ON UPDATE NO ACTION`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "user_profile" DROP CONSTRAINT "FK_51cb79b5555effaf7d69ba1cff9"`);
        await queryRunner.query(`DROP TABLE "user_profile"`);
    }

}
