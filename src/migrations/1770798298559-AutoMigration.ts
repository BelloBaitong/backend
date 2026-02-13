import { MigrationInterface, QueryRunner } from "typeorm";

export class AutoMigration1770798298559 implements MigrationInterface {
    name = 'AutoMigration1770798298559'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`CREATE TABLE "chat_sessions" ("id" uuid NOT NULL DEFAULT uuid_generate_v4(), "title" character varying NOT NULL, "userId" integer NOT NULL, "createdAt" TIMESTAMP NOT NULL DEFAULT now(), "updatedAt" TIMESTAMP NOT NULL DEFAULT now(), CONSTRAINT "PK_efc151a4aafa9a28b73dedc485f" PRIMARY KEY ("id"))`);
        await queryRunner.query(`CREATE TABLE "chat_messages" ("id" uuid NOT NULL DEFAULT uuid_generate_v4(), "role" character varying NOT NULL, "content" text NOT NULL, "sources" jsonb, "createdAt" TIMESTAMP NOT NULL DEFAULT now(), "sessionId" uuid, CONSTRAINT "PK_40c55ee0e571e268b0d3cd37d10" PRIMARY KEY ("id"))`);
        await queryRunner.query(`ALTER TABLE "chat_sessions" ADD CONSTRAINT "FK_d0320df1059d8a029a460f4161d" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE ON UPDATE NO ACTION`);
        await queryRunner.query(`ALTER TABLE "chat_messages" ADD CONSTRAINT "FK_a82476a8acdd6cd6936378cb72d" FOREIGN KEY ("sessionId") REFERENCES "chat_sessions"("id") ON DELETE CASCADE ON UPDATE NO ACTION`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "chat_messages" DROP CONSTRAINT "FK_a82476a8acdd6cd6936378cb72d"`);
        await queryRunner.query(`ALTER TABLE "chat_sessions" DROP CONSTRAINT "FK_d0320df1059d8a029a460f4161d"`);
        await queryRunner.query(`DROP TABLE "chat_messages"`);
        await queryRunner.query(`DROP TABLE "chat_sessions"`);
    }

}
