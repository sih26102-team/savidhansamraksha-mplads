import { Router, type IRouter } from "express";
import healthRouter from "./health";
import authRouter from "./auth";
import administrationRouter from "./administration";
import dashboardRouter from "./dashboard";
import projectsRouter from "./projects";
import auditRouter from "./audit";

const router: IRouter = Router();

router.use(healthRouter);
router.use(authRouter);
router.use(administrationRouter);
router.use(dashboardRouter);
router.use(projectsRouter);
router.use(auditRouter);

export default router;
